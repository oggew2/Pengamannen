"""User portfolio management - holdings, performance, history."""
import json
from datetime import date, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session


def get_portfolio_value(db: Session, portfolio_id: int) -> Dict:
    """Get current portfolio holdings with market values."""
    from models import UserPortfolioAccount, Stock, DailyPrice
    
    account = db.query(UserPortfolioAccount).filter(UserPortfolioAccount.id == portfolio_id).first()
    if not account:
        return {"error": "Portfolio not found", "holdings": [], "total_value": 0}
    
    holdings = json.loads(account.holdings_json or "[]")
    
    result = []
    total_value = 0
    
    for h in holdings:
        ticker = h.get('ticker', '')
        shares = h.get('shares', 0)
        avg_price = h.get('avg_price', 0)
        
        # Get current price
        price_row = db.query(DailyPrice).filter(
            DailyPrice.ticker == ticker
        ).order_by(DailyPrice.date.desc()).first()
        
        current_price = price_row.close if price_row else avg_price
        market_value = shares * current_price
        cost_basis = shares * avg_price
        gain_loss = market_value - cost_basis if avg_price > 0 else 0
        gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
        
        # Get stock info
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        
        result.append({
            'ticker': ticker,
            'name': stock.name if stock else ticker,
            'shares': shares,
            'avg_price': avg_price,
            'current_price': current_price,
            'market_value': round(market_value, 2),
            'cost_basis': round(cost_basis, 2),
            'gain_loss': round(gain_loss, 2),
            'gain_loss_pct': round(gain_loss_pct, 2),
            'weight': 0  # Will be calculated after total
        })
        total_value += market_value
    
    # Calculate weights
    for h in result:
        h['weight'] = round(h['market_value'] / total_value * 100, 2) if total_value > 0 else 0
    
    return {
        'portfolio_id': portfolio_id,
        'name': account.name,
        'holdings': result,
        'total_value': round(total_value, 2),
        'total_cost': round(sum(h['cost_basis'] for h in result), 2),
        'total_gain_loss': round(sum(h['gain_loss'] for h in result), 2)
    }


def calculate_portfolio_performance(db: Session, portfolio_id: int, days: int = 252) -> Dict:
    """Calculate portfolio performance metrics."""
    from models import UserPortfolioAccount, DailyPrice
    import numpy as np
    
    account = db.query(UserPortfolioAccount).filter(UserPortfolioAccount.id == portfolio_id).first()
    if not account:
        return {"error": "Portfolio not found"}
    
    holdings = json.loads(account.holdings_json or "[]")
    if not holdings:
        return {"error": "No holdings in portfolio"}
    
    tickers = [h['ticker'] for h in holdings]
    weights = {h['ticker']: h.get('shares', 0) for h in holdings}
    
    # Get price history
    cutoff = date.today() - timedelta(days=days)
    prices = db.query(DailyPrice).filter(
        DailyPrice.ticker.in_(tickers),
        DailyPrice.date >= cutoff
    ).order_by(DailyPrice.date).all()
    
    if not prices:
        return {"error": "No price data available"}
    
    # Build price matrix
    from collections import defaultdict
    price_by_date = defaultdict(dict)
    for p in prices:
        price_by_date[p.date][p.ticker] = p.close
    
    dates = sorted(price_by_date.keys())
    
    # Calculate portfolio values
    portfolio_values = []
    for d in dates:
        day_value = sum(
            price_by_date[d].get(t, 0) * weights.get(t, 0)
            for t in tickers
        )
        if day_value > 0:
            portfolio_values.append({'date': d.isoformat(), 'value': day_value})
    
    if len(portfolio_values) < 2:
        return {"error": "Insufficient data for performance calculation"}
    
    values = [p['value'] for p in portfolio_values]
    returns = np.diff(values) / values[:-1]
    
    total_return = (values[-1] / values[0] - 1) * 100
    annualized_return = ((values[-1] / values[0]) ** (252 / len(values)) - 1) * 100
    volatility = np.std(returns) * np.sqrt(252) * 100
    sharpe = annualized_return / volatility if volatility > 0 else 0
    
    # Max drawdown
    peak = np.maximum.accumulate(values)
    drawdown = (np.array(values) - peak) / peak
    max_drawdown = np.min(drawdown) * 100
    
    return {
        'portfolio_id': portfolio_id,
        'period_days': len(values),
        'total_return_pct': round(total_return, 2),
        'annualized_return_pct': round(annualized_return, 2),
        'volatility_pct': round(volatility, 2),
        'sharpe_ratio': round(sharpe, 2),
        'max_drawdown_pct': round(max_drawdown, 2),
        'portfolio_values': portfolio_values
    }


def get_portfolio_history(db: Session, portfolio_id: int, days: int = 365) -> Dict:
    """Get portfolio value history for charting."""
    from models import UserPortfolioAccount, DailyPrice
    
    account = db.query(UserPortfolioAccount).filter(UserPortfolioAccount.id == portfolio_id).first()
    if not account:
        return {"error": "Portfolio not found", "history": []}
    
    holdings = json.loads(account.holdings_json or "[]")
    if not holdings:
        return {"history": [], "message": "No holdings"}
    
    tickers = [h['ticker'] for h in holdings]
    weights = {h['ticker']: h.get('shares', 0) for h in holdings}
    
    cutoff = date.today() - timedelta(days=days)
    prices = db.query(DailyPrice).filter(
        DailyPrice.ticker.in_(tickers),
        DailyPrice.date >= cutoff
    ).order_by(DailyPrice.date).all()
    
    from collections import defaultdict
    price_by_date = defaultdict(dict)
    for p in prices:
        price_by_date[p.date][p.ticker] = p.close
    
    history = []
    for d in sorted(price_by_date.keys()):
        value = sum(
            price_by_date[d].get(t, 0) * weights.get(t, 0)
            for t in tickers
        )
        if value > 0:
            history.append({'date': d.isoformat(), 'value': round(value, 2)})
    
    return {
        'portfolio_id': portfolio_id,
        'history': history,
        'start_date': history[0]['date'] if history else None,
        'end_date': history[-1]['date'] if history else None,
        'data_points': len(history)
    }


def save_snapshot(db: Session, portfolio_id: int) -> int:
    """Save current portfolio state as a snapshot."""
    from models import UserPortfolioAccount, PortfolioSnapshot
    import json
    
    # Get current holdings with values
    holdings_data = get_portfolio_value(db, portfolio_id)
    
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=date.today(),
        total_value=holdings_data.get('total_value', 0),
        cash=0,
        holdings_json=json.dumps(holdings_data.get('holdings', []))
    )
    db.add(snapshot)
    db.commit()
    
    return snapshot.id


def calculate_rebalance_trades(db: Session, portfolio_id: int, target_holdings: List[str], portfolio_value: float = None) -> Dict:
    """Calculate trades needed to rebalance portfolio."""
    from models import UserPortfolioAccount, Stock, DailyPrice
    import json
    
    account = db.query(UserPortfolioAccount).filter(UserPortfolioAccount.id == portfolio_id).first()
    if not account:
        return {"error": "Portfolio not found"}
    
    current_holdings = json.loads(account.holdings_json or "[]")
    
    # Get current portfolio value if not provided
    if portfolio_value is None:
        holdings_data = get_portfolio_value(db, portfolio_id)
        portfolio_value = holdings_data.get('total_value', 0)
    
    if portfolio_value <= 0:
        return {"error": "Portfolio value must be positive"}
    
    # Target allocation (equal weight)
    target_per_stock = portfolio_value / len(target_holdings) if target_holdings else 0
    
    # Current holdings map
    current_map = {}
    for h in current_holdings:
        ticker = h.get('ticker')
        shares = h.get('shares', 0)
        price_row = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).first()
        price = price_row.close if price_row else 0
        current_map[ticker] = {'shares': shares, 'value': shares * price, 'price': price}
    
    trades = []
    
    # Sells (stocks not in target)
    for ticker, data in current_map.items():
        if ticker not in target_holdings and data['value'] > 0:
            trades.append({
                'ticker': ticker,
                'action': 'SELL',
                'shares': data['shares'],
                'amount_sek': data['value'],
                'price': data['price']
            })
    
    # Buys and rebalances
    for ticker in target_holdings:
        current = current_map.get(ticker, {'value': 0, 'price': 0})
        diff = target_per_stock - current['value']
        
        price_row = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).first()
        price = price_row.close if price_row else current['price']
        
        if abs(diff) > 100 and price > 0:
            shares = int(abs(diff) / price)
            if shares > 0:
                trades.append({
                    'ticker': ticker,
                    'action': 'BUY' if diff > 0 else 'SELL',
                    'shares': shares,
                    'amount_sek': shares * price,
                    'price': price
                })
    
    return {
        'portfolio_id': portfolio_id,
        'portfolio_value': portfolio_value,
        'target_holdings': target_holdings,
        'trades': trades,
        'total_buys': sum(t['amount_sek'] for t in trades if t['action'] == 'BUY'),
        'total_sells': sum(t['amount_sek'] for t in trades if t['action'] == 'SELL')
    }
