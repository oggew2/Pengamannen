"""Portfolio tracking service - track holdings, transactions, and performance."""
from datetime import date, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import json

from models import UserPortfolio, PortfolioTransaction, PortfolioSnapshot, DailyPrice


def create_portfolio(db: Session, name: str = "Default") -> int:
    """Create a new portfolio."""
    portfolio = UserPortfolio(name=name)
    db.add(portfolio)
    db.commit()
    return portfolio.id


def add_transaction(
    db: Session,
    portfolio_id: int,
    ticker: str,
    transaction_type: str,
    shares: float,
    price: float,
    transaction_date: date,
    strategy: str = None,
    fees: float = 0,
    notes: str = None
) -> int:
    """Record a buy/sell transaction."""
    txn = PortfolioTransaction(
        portfolio_id=portfolio_id,
        ticker=ticker,
        transaction_type=transaction_type.upper(),
        shares=shares,
        price=price,
        fees=fees,
        transaction_date=transaction_date,
        strategy=strategy,
        notes=notes
    )
    db.add(txn)
    db.commit()
    return txn.id


def get_current_holdings(db: Session, portfolio_id: int) -> Dict[str, float]:
    """Calculate current holdings from transactions."""
    txns = db.query(PortfolioTransaction).filter(
        PortfolioTransaction.portfolio_id == portfolio_id
    ).order_by(PortfolioTransaction.transaction_date).all()
    
    holdings = {}
    for txn in txns:
        if txn.ticker not in holdings:
            holdings[txn.ticker] = 0
        if txn.transaction_type == "BUY":
            holdings[txn.ticker] += txn.shares
        elif txn.transaction_type == "SELL":
            holdings[txn.ticker] -= txn.shares
    
    # Remove zero holdings
    return {k: v for k, v in holdings.items() if v > 0}


def get_portfolio_value(db: Session, portfolio_id: int, as_of_date: date = None) -> Dict:
    """Calculate portfolio value with current prices."""
    holdings = get_current_holdings(db, portfolio_id)
    if not holdings:
        return {"total_value": 0, "holdings": [], "cash": 0}
    
    as_of_date = as_of_date or date.today()
    
    # Get latest prices
    result = []
    total_value = 0
    
    for ticker, shares in holdings.items():
        price_record = db.query(DailyPrice).filter(
            DailyPrice.ticker == ticker,
            DailyPrice.date <= as_of_date
        ).order_by(DailyPrice.date.desc()).first()
        
        price = price_record.close if price_record else 0
        value = shares * price
        total_value += value
        
        result.append({
            "ticker": ticker,
            "shares": shares,
            "price": price,
            "value": value
        })
    
    # Calculate weights
    for h in result:
        h["weight"] = h["value"] / total_value if total_value > 0 else 0
    
    return {
        "total_value": total_value,
        "holdings": sorted(result, key=lambda x: -x["value"]),
        "as_of_date": as_of_date.isoformat()
    }


def calculate_portfolio_performance(db: Session, portfolio_id: int) -> Dict:
    """Calculate portfolio performance metrics."""
    txns = db.query(PortfolioTransaction).filter(
        PortfolioTransaction.portfolio_id == portfolio_id
    ).order_by(PortfolioTransaction.transaction_date).all()
    
    if not txns:
        return {"error": "No transactions found"}
    
    # Calculate cost basis
    cost_basis = {}
    total_invested = 0
    total_fees = 0
    
    for txn in txns:
        if txn.transaction_type == "BUY":
            if txn.ticker not in cost_basis:
                cost_basis[txn.ticker] = {"shares": 0, "cost": 0}
            cost_basis[txn.ticker]["shares"] += txn.shares
            cost_basis[txn.ticker]["cost"] += txn.shares * txn.price
            total_invested += txn.shares * txn.price
        total_fees += txn.fees or 0
    
    # Current value
    current = get_portfolio_value(db, portfolio_id)
    current_value = current["total_value"]
    
    # Calculate gains
    total_cost = sum(cb["cost"] for cb in cost_basis.values())
    unrealized_gain = current_value - total_cost
    unrealized_gain_pct = (unrealized_gain / total_cost * 100) if total_cost > 0 else 0
    
    # Per-holding performance
    holdings_perf = []
    for h in current["holdings"]:
        ticker = h["ticker"]
        if ticker in cost_basis and cost_basis[ticker]["shares"] > 0:
            avg_cost = cost_basis[ticker]["cost"] / cost_basis[ticker]["shares"]
            gain = (h["price"] - avg_cost) * h["shares"]
            gain_pct = (h["price"] / avg_cost - 1) * 100 if avg_cost > 0 else 0
            holdings_perf.append({
                **h,
                "avg_cost": avg_cost,
                "gain": gain,
                "gain_pct": gain_pct
            })
    
    return {
        "total_invested": total_invested,
        "current_value": current_value,
        "total_fees": total_fees,
        "unrealized_gain": unrealized_gain,
        "unrealized_gain_pct": unrealized_gain_pct,
        "holdings": holdings_perf,
        "first_transaction": txns[0].transaction_date.isoformat(),
        "last_transaction": txns[-1].transaction_date.isoformat()
    }


def calculate_rebalance_trades(
    db: Session,
    portfolio_id: int,
    target_holdings: List[Dict],
    portfolio_value: float = None
) -> List[Dict]:
    """
    Calculate trades needed to rebalance to target holdings.
    
    Args:
        target_holdings: List of {ticker, weight} for target allocation
        portfolio_value: Total value to allocate (uses current if not provided)
    """
    current = get_portfolio_value(db, portfolio_id)
    portfolio_value = portfolio_value or current["total_value"]
    
    if portfolio_value <= 0:
        return []
    
    # Current holdings by ticker
    current_by_ticker = {h["ticker"]: h for h in current["holdings"]}
    
    trades = []
    
    for target in target_holdings:
        ticker = target["ticker"]
        target_weight = target.get("weight", 0.1)  # Default 10% per position
        target_value = portfolio_value * target_weight
        
        current_holding = current_by_ticker.get(ticker, {"shares": 0, "value": 0, "price": 0})
        current_value = current_holding["value"]
        
        diff_value = target_value - current_value
        
        if abs(diff_value) < 100:  # Skip small trades
            continue
        
        # Get current price
        price = current_holding.get("price", 0)
        if price <= 0:
            price_record = db.query(DailyPrice).filter(
                DailyPrice.ticker == ticker
            ).order_by(DailyPrice.date.desc()).first()
            price = price_record.close if price_record else 0
        
        if price <= 0:
            continue
        
        shares = abs(diff_value) / price
        
        trades.append({
            "ticker": ticker,
            "action": "BUY" if diff_value > 0 else "SELL",
            "shares": round(shares, 2),
            "estimated_value": abs(diff_value),
            "current_weight": current_value / portfolio_value if portfolio_value > 0 else 0,
            "target_weight": target_weight,
            "price": price
        })
    
    # Add sells for positions not in target
    target_tickers = {t["ticker"] for t in target_holdings}
    for ticker, holding in current_by_ticker.items():
        if ticker not in target_tickers and holding["shares"] > 0:
            trades.append({
                "ticker": ticker,
                "action": "SELL",
                "shares": holding["shares"],
                "estimated_value": holding["value"],
                "current_weight": holding["weight"],
                "target_weight": 0,
                "price": holding["price"]
            })
    
    return sorted(trades, key=lambda x: -x["estimated_value"])


def save_snapshot(db: Session, portfolio_id: int) -> int:
    """Save current portfolio state as a snapshot."""
    current = get_portfolio_value(db, portfolio_id)
    
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=date.today(),
        total_value=current["total_value"],
        cash=0,
        holdings_json=json.dumps(current["holdings"])
    )
    db.add(snapshot)
    db.commit()
    return snapshot.id


def get_portfolio_history(db: Session, portfolio_id: int) -> List[Dict]:
    """Get portfolio value history from snapshots."""
    snapshots = db.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.portfolio_id == portfolio_id
    ).order_by(PortfolioSnapshot.snapshot_date).all()
    
    return [{
        "date": s.snapshot_date.isoformat(),
        "value": s.total_value
    } for s in snapshots]
