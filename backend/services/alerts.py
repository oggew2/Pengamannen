"""Smart alerts service - rebalancing reminders, portfolio milestones, volatility warnings."""
from datetime import date, timedelta
from typing import List, Dict
from models import Stock, DailyPrice, Fundamentals
from sqlalchemy.orm import Session


def check_rebalancing_alerts(db: Session) -> List[Dict]:
    """Check if any strategies need rebalancing soon."""
    alerts = []
    today = date.today()
    
    # Strategy rebalance schedules
    schedules = {
        'sammansatt_momentum': [3, 6, 9, 12],  # Quarterly
        'trendande_varde': [1],  # January
        'trendande_utdelning': [2],  # February
        'trendande_kvalitet': [3],  # March
    }
    
    for strategy, months in schedules.items():
        for month in months:
            rebalance_date = date(today.year if month >= today.month else today.year + 1, month, 1)
            days_until = (rebalance_date - today).days
            
            if 0 <= days_until <= 7:
                alerts.append({
                    'type': 'rebalance_due',
                    'strategy': strategy,
                    'date': rebalance_date.isoformat(),
                    'days_until': days_until,
                    'priority': 'high' if days_until <= 2 else 'medium',
                    'message': f"{strategy.replace('_', ' ').title()} rebalancing in {days_until} days"
                })
    
    return alerts


def check_volatility_alerts(db: Session, threshold: float = 3.0) -> List[Dict]:
    """Check for unusual market volatility."""
    alerts = []
    
    # Get recent prices for top stocks
    recent = db.query(DailyPrice).order_by(DailyPrice.date.desc()).limit(500).all()
    
    from collections import defaultdict
    by_ticker = defaultdict(list)
    for p in recent:
        by_ticker[p.ticker].append(p.close)
    
    for ticker, prices in by_ticker.items():
        if len(prices) < 5:
            continue
        
        # Calculate daily returns
        returns = [(prices[i] - prices[i+1]) / prices[i+1] * 100 for i in range(min(5, len(prices)-1))]
        
        # Check for large moves
        for i, ret in enumerate(returns):
            if abs(ret) >= threshold:
                alerts.append({
                    'type': 'volatility',
                    'ticker': ticker,
                    'change_pct': round(ret, 2),
                    'priority': 'high' if abs(ret) >= 5 else 'medium',
                    'message': f"{ticker} moved {ret:+.1f}% recently"
                })
                break  # One alert per ticker
    
    return alerts[:10]  # Limit to top 10


def check_portfolio_milestones(holdings: List[Dict], total_value: float) -> List[Dict]:
    """Check for portfolio value milestones."""
    alerts = []
    
    milestones = [100000, 250000, 500000, 1000000, 2500000, 5000000]
    
    for m in milestones:
        if total_value >= m * 0.95 and total_value <= m * 1.05:
            alerts.append({
                'type': 'milestone',
                'value': m,
                'current': round(total_value, 0),
                'priority': 'low',
                'message': f"Portfolio approaching {m:,} SEK milestone!"
            })
            break
    
    return alerts


def get_all_alerts(db: Session, holdings: List[Dict] = None, total_value: float = 0) -> Dict:
    """Get all active alerts."""
    alerts = []
    
    alerts.extend(check_rebalancing_alerts(db))
    alerts.extend(check_volatility_alerts(db))
    
    if holdings and total_value:
        alerts.extend(check_portfolio_milestones(holdings, total_value))
    
    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    alerts.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))
    
    return {
        'alerts': alerts,
        'count': len(alerts),
        'has_high_priority': any(a.get('priority') == 'high' for a in alerts)
    }
