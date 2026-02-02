"""Parse broker CSV exports with ISIN matching and duplicate detection."""
import csv
import hashlib
from io import StringIO
from datetime import datetime
from typing import Optional


def generate_transaction_hash(date: str, isin: str, txn_type: str, shares: float, price: float) -> str:
    """Generate unique hash for duplicate detection."""
    # Normalize values for consistent hashing
    data = f"{date}|{isin}|{txn_type}|{float(shares)}|{round(float(price), 2)}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def parse_avanza_csv(content: str, isin_lookup: Optional[dict] = None) -> list[dict]:
    """
    Parse Avanza transaction CSV with ISIN matching.
    
    Handles:
    - Semicolon delimiter (Avanza default)
    - BOM character at start
    - Swedish number format (comma decimal, space thousands)
    - Multiple currency columns (Transaktionsvaluta, Instrumentvaluta)
    - Negative Antal for sells
    - Empty Valutakurs fields
    
    Args:
        content: CSV content string
        isin_lookup: Dict mapping ISIN -> {ticker, name, currency}
    
    Returns:
        List of parsed transactions with ticker matching
    """
    transactions = []
    
    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]
    
    reader = csv.DictReader(StringIO(content), delimiter=';')
    
    for row in reader:
        txn_type = row.get('Typ av transaktion', '').strip()
        # Normalize transaction type - accept various formats
        txn_type_lower = txn_type.lower()
        if txn_type_lower in ('köp', 'kop', 'buy'):
            txn_type = 'Köp'
        elif txn_type_lower in ('sälj', 'salj', 'sell'):
            txn_type = 'Sälj'
        else:
            continue  # Skip dividends, fees, etc.
        
        # Parse numeric fields with Swedish format (comma decimal, space thousands)
        def parse_num(val: str) -> float:
            if not val or val.strip() == '':
                return 0.0
            # Remove spaces and non-breaking spaces, replace comma with dot
            cleaned = val.replace(',', '.').replace(' ', '').replace('\xa0', '')
            try:
                return abs(float(cleaned))
            except ValueError:
                return 0.0
        
        isin = row.get('ISIN', '').strip()
        date = row.get('Datum', '').strip()
        
        # Antal can be negative for sells in Avanza export
        antal_raw = row.get('Antal', '0')
        shares = parse_num(antal_raw)
        
        price = parse_num(row.get('Kurs', '0'))
        fee = parse_num(row.get('Courtage', '0'))
        
        # FX rate - use 1.0 if empty or missing
        fx_rate_raw = row.get('Valutakurs', '')
        fx_rate = parse_num(fx_rate_raw) if fx_rate_raw.strip() else 1.0
        if fx_rate == 0:
            fx_rate = 1.0
        
        # Currency: prefer Instrumentvaluta, fallback to Transaktionsvaluta
        currency = (row.get('Instrumentvaluta', '') or row.get('Transaktionsvaluta', 'SEK')).strip() or 'SEK'
        
        # Match ISIN to ticker
        ticker = None
        name = row.get('Värdepapper/beskrivning', row.get('Värdepapper', '')).strip()
        if isin_lookup and isin:
            lookup = isin_lookup.get(isin)
            if lookup:
                ticker = lookup.get('ticker')
                if not name:
                    name = lookup.get('name', '')
        
        # Calculate SEK price
        # If currency is SEK, price is already in SEK
        # If currency is foreign and fx_rate > 1, price_sek = price * fx_rate
        if currency == 'SEK':
            price_sek = price
        else:
            price_sek = price * fx_rate
        
        # Generate hash for duplicate detection
        txn_type_norm = 'BUY' if txn_type in ('Köp', 'Buy') else 'SELL'
        tx_hash = generate_transaction_hash(date, isin, txn_type_norm, shares, price)
        
        transactions.append({
            'date': date,
            'ticker': ticker,
            'name': name,
            'isin': isin,
            'type': txn_type_norm,
            'shares': shares,
            'price_local': price,
            'price_sek': price_sek,
            'currency': currency,
            'fee': fee,
            'fx_rate': fx_rate,
            'hash': tx_hash,
        })
    
    return transactions


def calculate_positions(transactions: list[dict]) -> dict:
    """
    Calculate current positions from transaction history using average cost method.
    
    Uses ticker if available, falls back to ISIN for grouping.
    
    Returns:
        Dict of key -> {shares, avg_price_sek, total_cost, total_fees, currency, name, isin, first_buy_date}
    """
    positions = {}
    
    # Sort by date
    sorted_txns = sorted(transactions, key=lambda x: x.get('date', ''))
    
    for txn in sorted_txns:
        # Use ticker if available, otherwise use ISIN as key
        key = txn.get('ticker') or txn.get('isin')
        if not key:
            continue
        
        if key not in positions:
            positions[key] = {
                'shares': 0,
                'total_cost': 0,
                'total_fees': 0,
                'currency': txn.get('currency', 'SEK'),
                'isin': txn.get('isin'),
                'name': txn.get('name'),
                'ticker': txn.get('ticker'),
                'first_buy_date': None,
            }
        
        pos = positions[key]
        shares = txn.get('shares', 0)
        price_sek = txn.get('price_sek', 0)
        fee = txn.get('fee', 0)
        
        # Update name if we have a better one
        if txn.get('name') and not pos.get('name'):
            pos['name'] = txn['name']
        
        if txn.get('type') == 'BUY':
            pos['total_cost'] += shares * price_sek
            pos['shares'] += shares
            pos['total_fees'] += fee
            if not pos['first_buy_date']:
                pos['first_buy_date'] = txn.get('date')
        else:  # SELL
            if pos['shares'] > 0:
                # Reduce cost proportionally
                sell_ratio = min(shares / pos['shares'], 1.0)
                pos['total_cost'] -= pos['total_cost'] * sell_ratio
            pos['shares'] -= shares
            pos['total_fees'] += fee
    
    # Calculate average prices and handle edge cases
    result = {}
    for key, pos in positions.items():
        if pos['shares'] > 0:
            pos['avg_price_sek'] = pos['total_cost'] / pos['shares']
            result[key] = pos
        elif pos['shares'] < 0:
            # Negative position - missing buy history
            pos['avg_price_sek'] = 0
            pos['warning'] = 'negative_position'
            result[key] = pos
        # Zero positions are excluded
    
    return result


def filter_duplicates(transactions: list[dict], existing_hashes: set) -> tuple[list[dict], list[dict]]:
    """
    Filter out duplicate transactions.
    
    Returns:
        (new_transactions, duplicate_transactions)
    """
    new = []
    duplicates = []
    
    for txn in transactions:
        if txn.get('hash') in existing_hashes:
            duplicates.append(txn)
        else:
            new.append(txn)
    
    return new, duplicates


# Aliases for backward compatibility
parse_broker_csv = parse_avanza_csv


def calculate_holdings_from_transactions(transactions: list[dict]) -> dict:
    """Calculate current holdings from transaction history (legacy)."""
    holdings = {}
    for txn in transactions:
        ticker = txn.get('ticker', '').strip().upper()
        if not ticker:
            continue
        shares = txn.get('shares', 0)
        if txn.get('type') == 'SELL':
            shares = -shares
        holdings[ticker] = holdings.get(ticker, 0) + shares
    
    return {k: v for k, v in holdings.items() if v > 0}
