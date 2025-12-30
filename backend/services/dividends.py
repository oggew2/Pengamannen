"""Dividend calendar and income tracking service."""
from datetime import date, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session

from models import DividendEvent, DailyPrice


def add_dividend_event(
    db: Session,
    ticker: str,
    ex_date: date,
    amount: float,
    payment_date: date = None,
    dividend_type: str = "regular"
) -> int:
    """Add a dividend event."""
    event = DividendEvent(
        ticker=ticker,
        ex_date=ex_date,
        payment_date=payment_date or ex_date + timedelta(days=14),
        amount=amount,
        dividend_type=dividend_type
    )
    db.add(event)
    db.commit()
    return event.id


def get_upcoming_dividends(
    db: Session,
    tickers: List[str] = None,
    days_ahead: int = 90
) -> List[Dict]:
    """Get upcoming dividend events."""
    today = date.today()
    end_date = today + timedelta(days=days_ahead)
    
    query = db.query(DividendEvent).filter(
        DividendEvent.ex_date >= today,
        DividendEvent.ex_date <= end_date
    )
    
    if tickers:
        query = query.filter(DividendEvent.ticker.in_(tickers))
    
    events = query.order_by(DividendEvent.ex_date).all()
    
    return [{
        "ticker": e.ticker,
        "ex_date": e.ex_date.isoformat(),
        "payment_date": e.payment_date.isoformat() if e.payment_date else None,
        "amount": e.amount,
        "type": e.dividend_type,
        "days_until_ex": (e.ex_date - today).days
    } for e in events]


def calculate_projected_income(
    db: Session,
    holdings: List[Dict],
    months_ahead: int = 12
) -> Dict:
    """
    Calculate projected dividend income from holdings.
    
    Args:
        holdings: List of {ticker, shares}
    """
    if not holdings:
        return {"total_annual": 0, "monthly": [], "by_stock": []}
    
    tickers = [h["ticker"] for h in holdings]
    shares_by_ticker = {h["ticker"]: h["shares"] for h in holdings}
    
    # Get historical dividends to estimate future
    one_year_ago = date.today() - timedelta(days=365)
    past_dividends = db.query(DividendEvent).filter(
        DividendEvent.ticker.in_(tickers),
        DividendEvent.ex_date >= one_year_ago
    ).all()
    
    # Calculate annual dividend per ticker
    annual_div = {}
    for d in past_dividends:
        if d.ticker not in annual_div:
            annual_div[d.ticker] = 0
        annual_div[d.ticker] += d.amount
    
    # Project income
    by_stock = []
    total_annual = 0
    
    for ticker, shares in shares_by_ticker.items():
        div_per_share = annual_div.get(ticker, 0)
        annual_income = div_per_share * shares
        total_annual += annual_income
        
        if div_per_share > 0:
            by_stock.append({
                "ticker": ticker,
                "shares": shares,
                "div_per_share": round(div_per_share, 2),
                "annual_income": round(annual_income, 2)
            })
    
    # Estimate monthly (assume even distribution)
    monthly_avg = total_annual / 12
    
    return {
        "total_annual": round(total_annual, 2),
        "monthly_average": round(monthly_avg, 2),
        "by_stock": sorted(by_stock, key=lambda x: -x["annual_income"]),
        "yield_on_holdings": None  # Would need current value to calculate
    }


def get_dividend_history(
    db: Session,
    ticker: str,
    years: int = 5
) -> List[Dict]:
    """Get dividend history for a stock."""
    start_date = date.today() - timedelta(days=years * 365)
    
    events = db.query(DividendEvent).filter(
        DividendEvent.ticker == ticker,
        DividendEvent.ex_date >= start_date
    ).order_by(DividendEvent.ex_date.desc()).all()
    
    return [{
        "ex_date": e.ex_date.isoformat(),
        "payment_date": e.payment_date.isoformat() if e.payment_date else None,
        "amount": e.amount,
        "type": e.dividend_type
    } for e in events]


def calculate_dividend_growth(
    db: Session,
    ticker: str,
    years: int = 5
) -> Dict:
    """Calculate dividend growth rate."""
    history = get_dividend_history(db, ticker, years)
    
    if len(history) < 2:
        return {"growth_rate": None, "years": 0}
    
    # Group by year
    by_year = {}
    for d in history:
        year = d["ex_date"][:4]
        if year not in by_year:
            by_year[year] = 0
        by_year[year] += d["amount"]
    
    years_list = sorted(by_year.keys())
    if len(years_list) < 2:
        return {"growth_rate": None, "years": len(years_list)}
    
    # CAGR
    first_year = by_year[years_list[0]]
    last_year = by_year[years_list[-1]]
    num_years = len(years_list) - 1
    
    if first_year > 0 and last_year > 0:
        cagr = ((last_year / first_year) ** (1 / num_years) - 1) * 100
    else:
        cagr = None
    
    return {
        "growth_rate_pct": round(cagr, 1) if cagr else None,
        "years_of_data": len(years_list),
        "by_year": {y: round(v, 2) for y, v in by_year.items()}
    }
