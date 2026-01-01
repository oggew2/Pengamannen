"""Parse broker CSV exports."""
import csv
from io import StringIO


def parse_avanza_csv(content: str) -> list[dict]:
    """Parse Avanza transaction CSV."""
    transactions = []
    reader = csv.DictReader(StringIO(content), delimiter=';')
    
    for row in reader:
        txn_type = row.get('Typ av transaktion', '')
        if txn_type not in ('Köp', 'Sälj', 'Buy', 'Sell'):
            continue
        
        transactions.append({
            'date': row.get('Datum', ''),
            'ticker': row.get('Värdepapper', ''),
            'type': 'BUY' if txn_type in ('Köp', 'Buy') else 'SELL',
            'shares': abs(float(row.get('Antal', '0').replace(',', '.').replace(' ', '') or 0)),
            'price': abs(float(row.get('Kurs', '0').replace(',', '.').replace(' ', '') or 0)),
            'fees': abs(float(row.get('Courtage', '0').replace(',', '.').replace(' ', '') or 0))
        })
    
    return transactions


# Aliases for backward compatibility
parse_broker_csv = parse_avanza_csv


def calculate_holdings_from_transactions(transactions: list[dict]) -> dict:
    """Calculate current holdings from transaction history."""
    holdings = {}
    for txn in transactions:
        # Normalize ticker to uppercase for consistent matching
        ticker = txn.get('ticker', '').strip().upper()
        if not ticker:
            continue
        shares = txn.get('shares', 0)
        if txn.get('type') == 'SELL':
            shares = -shares
        holdings[ticker] = holdings.get(ticker, 0) + shares
    
    return {k: v for k, v in holdings.items() if v > 0}
