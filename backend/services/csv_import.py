"""
CSV Import service for broker transaction exports.

Supports:
- Avanza (Swedish broker) - Export from Min Ekonomi > Transaktioner > Exportera transaktioner
- Nordnet (Nordic broker)
- Generic CSV format

Avanza CSV columns (Swedish):
- Datum, Konto, Typ av transaktion, Värdepapper/beskrivning, Antal, Kurs, Belopp, Courtage, Valuta, ISIN
"""
import csv
import io
from datetime import datetime
from typing import List, Dict, Optional
import re


# Avanza transaction type mappings (Swedish -> English)
AVANZA_TRANSACTION_TYPES = {
    "Köp": "BUY",
    "Sälj": "SELL",
    "Utdelning": "DIVIDEND",
    "Insättning": "DEPOSIT",
    "Uttag": "WITHDRAWAL",
    "Ränta": "INTEREST",
    "Avgift": "FEE",
    "Preliminärskatt": "TAX",
    "Övrigt": "OTHER",
}

# Nordnet transaction type mappings
NORDNET_TRANSACTION_TYPES = {
    "KÖPT": "BUY",
    "SÅLT": "SELL",
    "UTDELNING": "DIVIDEND",
    "INSÄTTNING": "DEPOSIT",
    "UTTAG": "WITHDRAWAL",
}


def detect_broker_format(headers: List[str]) -> str:
    """Detect which broker format the CSV is from."""
    headers_lower = [h.lower().strip() for h in headers]
    
    # Avanza format
    if "värdepapper/beskrivning" in headers_lower or "värdepapper" in headers_lower:
        return "avanza"
    
    # Nordnet format
    if "verdipapir" in headers_lower or "värdepapper" in headers_lower and "id" in headers_lower:
        return "nordnet"
    
    # Generic format (English)
    if "ticker" in headers_lower or "symbol" in headers_lower:
        return "generic"
    
    return "unknown"


def parse_swedish_number(value: str) -> Optional[float]:
    """Parse Swedish number format (1 234,56 -> 1234.56)."""
    if not value or value.strip() == "-":
        return None
    
    # Remove spaces (thousand separator)
    value = value.replace(" ", "").replace("\xa0", "")
    # Replace comma with dot (decimal separator)
    value = value.replace(",", ".")
    
    try:
        return float(value)
    except ValueError:
        return None


def parse_swedish_date(value: str) -> Optional[str]:
    """Parse Swedish date format (YYYY-MM-DD)."""
    if not value:
        return None
    
    # Try common formats
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return value.strip()


def parse_avanza_csv(content: str) -> List[Dict]:
    """
    Parse Avanza transaction CSV export.
    
    Expected columns:
    Datum, Konto, Typ av transaktion, Värdepapper/beskrivning, Antal, Kurs, Belopp, Courtage, Valuta, ISIN
    """
    transactions = []
    
    # Handle BOM and encoding
    if content.startswith('\ufeff'):
        content = content[1:]
    
    reader = csv.DictReader(io.StringIO(content), delimiter=';')
    
    for row in reader:
        # Map column names (handle variations)
        date_col = row.get("Datum", row.get("datum", ""))
        account_col = row.get("Konto", row.get("konto", ""))
        type_col = row.get("Typ av transaktion", row.get("Transaktionstyp", ""))
        security_col = row.get("Värdepapper/beskrivning", row.get("Värdepapper", ""))
        quantity_col = row.get("Antal", row.get("antal", ""))
        price_col = row.get("Kurs", row.get("kurs", ""))
        amount_col = row.get("Belopp", row.get("belopp", ""))
        fee_col = row.get("Courtage", row.get("courtage", ""))
        currency_col = row.get("Valuta", row.get("valuta", "SEK"))
        isin_col = row.get("ISIN", row.get("isin", ""))
        
        # Parse transaction type
        tx_type = AVANZA_TRANSACTION_TYPES.get(type_col.strip(), "OTHER")
        
        # Only include buy/sell transactions for portfolio import
        if tx_type not in ["BUY", "SELL"]:
            continue
        
        # Extract ticker from security name (usually "NAME (TICKER)")
        ticker = None
        security_name = security_col.strip()
        ticker_match = re.search(r'\(([A-Z0-9\-\.]+)\)$', security_name)
        if ticker_match:
            ticker = ticker_match.group(1)
        
        transactions.append({
            "date": parse_swedish_date(date_col),
            "account": account_col.strip(),
            "type": tx_type,
            "security_name": security_name,
            "ticker": ticker,
            "isin": isin_col.strip() if isin_col else None,
            "quantity": parse_swedish_number(quantity_col),
            "price": parse_swedish_number(price_col),
            "amount": parse_swedish_number(amount_col),
            "fee": parse_swedish_number(fee_col) or 0,
            "currency": currency_col.strip() or "SEK",
            "source": "avanza"
        })
    
    return transactions


def parse_nordnet_csv(content: str) -> List[Dict]:
    """Parse Nordnet transaction CSV export."""
    transactions = []
    
    if content.startswith('\ufeff'):
        content = content[1:]
    
    # Nordnet uses tab or semicolon
    delimiter = '\t' if '\t' in content.split('\n')[0] else ';'
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    
    for row in reader:
        date_col = row.get("Bokföringsdag", row.get("Datum", ""))
        type_col = row.get("Transaktionstyp", row.get("Typ", ""))
        security_col = row.get("Värdepapper", row.get("Verdipapir", ""))
        quantity_col = row.get("Antal", row.get("Antall", ""))
        price_col = row.get("Kurs", "")
        amount_col = row.get("Belopp", row.get("Beløp", ""))
        fee_col = row.get("Avgifter", row.get("Courtage", ""))
        isin_col = row.get("ISIN", "")
        
        tx_type = NORDNET_TRANSACTION_TYPES.get(type_col.strip().upper(), "OTHER")
        
        if tx_type not in ["BUY", "SELL"]:
            continue
        
        transactions.append({
            "date": parse_swedish_date(date_col),
            "type": tx_type,
            "security_name": security_col.strip(),
            "ticker": None,
            "isin": isin_col.strip() if isin_col else None,
            "quantity": parse_swedish_number(quantity_col),
            "price": parse_swedish_number(price_col),
            "amount": parse_swedish_number(amount_col),
            "fee": parse_swedish_number(fee_col) or 0,
            "currency": "SEK",
            "source": "nordnet"
        })
    
    return transactions


def parse_generic_csv(content: str) -> List[Dict]:
    """Parse generic CSV with English column names."""
    transactions = []
    
    if content.startswith('\ufeff'):
        content = content[1:]
    
    # Try comma first, then semicolon
    delimiter = ',' if ',' in content.split('\n')[0] else ';'
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    
    for row in reader:
        # Flexible column name matching
        date = row.get("date", row.get("Date", row.get("DATE", "")))
        tx_type = row.get("type", row.get("Type", row.get("action", ""))).upper()
        ticker = row.get("ticker", row.get("Ticker", row.get("symbol", row.get("Symbol", ""))))
        quantity = row.get("quantity", row.get("Quantity", row.get("shares", row.get("Shares", ""))))
        price = row.get("price", row.get("Price", ""))
        fee = row.get("fee", row.get("Fee", row.get("commission", "0")))
        
        if tx_type not in ["BUY", "SELL"]:
            continue
        
        transactions.append({
            "date": date,
            "type": tx_type,
            "ticker": ticker.strip() if ticker else None,
            "quantity": float(quantity) if quantity else None,
            "price": float(price) if price else None,
            "fee": float(fee) if fee else 0,
            "currency": row.get("currency", "SEK"),
            "source": "generic"
        })
    
    return transactions


def parse_broker_csv(content: str, broker: str = None) -> Dict:
    """
    Parse broker CSV and return transactions.
    
    Args:
        content: CSV file content as string
        broker: Optional broker hint ('avanza', 'nordnet', 'generic')
    
    Returns:
        Dict with transactions and metadata
    """
    # Get headers to detect format
    lines = content.strip().split('\n')
    if not lines:
        return {"error": "Empty file", "transactions": []}
    
    # Detect delimiter
    first_line = lines[0]
    if ';' in first_line:
        headers = first_line.split(';')
    elif '\t' in first_line:
        headers = first_line.split('\t')
    else:
        headers = first_line.split(',')
    
    # Detect or use provided broker
    detected_broker = broker or detect_broker_format(headers)
    
    # Parse based on format
    if detected_broker == "avanza":
        transactions = parse_avanza_csv(content)
    elif detected_broker == "nordnet":
        transactions = parse_nordnet_csv(content)
    elif detected_broker == "generic":
        transactions = parse_generic_csv(content)
    else:
        # Try Avanza format as default for Swedish brokers
        transactions = parse_avanza_csv(content)
        if not transactions:
            transactions = parse_generic_csv(content)
    
    return {
        "broker": detected_broker,
        "transactions": transactions,
        "count": len(transactions),
        "buy_count": len([t for t in transactions if t["type"] == "BUY"]),
        "sell_count": len([t for t in transactions if t["type"] == "SELL"])
    }


def calculate_holdings_from_transactions(transactions: List[Dict]) -> List[Dict]:
    """
    Calculate current holdings from transaction history.
    Uses FIFO (First In, First Out) for cost basis.
    """
    holdings = {}  # ticker -> {shares, cost_basis, transactions}
    
    # Sort by date
    sorted_txns = sorted(transactions, key=lambda x: x.get("date", ""))
    
    for txn in sorted_txns:
        ticker = txn.get("ticker") or txn.get("isin") or txn.get("security_name")
        if not ticker:
            continue
        
        quantity = txn.get("quantity") or 0
        price = txn.get("price") or 0
        fee = txn.get("fee") or 0
        
        if ticker not in holdings:
            holdings[ticker] = {
                "shares": 0,
                "total_cost": 0,
                "lots": []  # For FIFO tracking
            }
        
        if txn["type"] == "BUY":
            holdings[ticker]["shares"] += quantity
            holdings[ticker]["total_cost"] += (quantity * price) + fee
            holdings[ticker]["lots"].append({
                "date": txn.get("date"),
                "shares": quantity,
                "price": price
            })
        
        elif txn["type"] == "SELL":
            holdings[ticker]["shares"] -= quantity
            # FIFO: remove from oldest lots first
            shares_to_remove = quantity
            while shares_to_remove > 0 and holdings[ticker]["lots"]:
                lot = holdings[ticker]["lots"][0]
                if lot["shares"] <= shares_to_remove:
                    shares_to_remove -= lot["shares"]
                    holdings[ticker]["total_cost"] -= lot["shares"] * lot["price"]
                    holdings[ticker]["lots"].pop(0)
                else:
                    lot["shares"] -= shares_to_remove
                    holdings[ticker]["total_cost"] -= shares_to_remove * lot["price"]
                    shares_to_remove = 0
    
    # Convert to list, filter out zero holdings
    result = []
    for ticker, data in holdings.items():
        if data["shares"] > 0.001:  # Small threshold for floating point
            avg_cost = data["total_cost"] / data["shares"] if data["shares"] > 0 else 0
            result.append({
                "ticker": ticker,
                "shares": round(data["shares"], 4),
                "avg_cost": round(avg_cost, 2),
                "total_cost": round(data["total_cost"], 2)
            })
    
    return sorted(result, key=lambda x: -x["total_cost"])
