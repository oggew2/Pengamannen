"""Email report service - sends scheduled reports to users."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Rebalance schedule
REBALANCE_SCHEDULE = {
    'sammansatt_momentum': {'months': [3, 6, 9, 12], 'day': 1},  # Quarterly
    'trendande_varde': {'months': [3], 'day': 1},  # Annual March
    'trendande_utdelning': {'months': [3], 'day': 1},  # Annual March
    'trendande_kvalitet': {'months': [3], 'day': 1},  # Annual March
}


def get_next_rebalance_date(strategy: str) -> Optional[date]:
    """Get next rebalance date for a strategy."""
    schedule = REBALANCE_SCHEDULE.get(strategy)
    if not schedule:
        return None
    
    today = date.today()
    for month in sorted(schedule['months']):
        rebal_date = date(today.year, month, schedule['day'])
        if rebal_date > today:
            return rebal_date
    # Next year
    return date(today.year + 1, schedule['months'][0], schedule['day'])


def days_until_rebalance(strategy: str) -> Optional[int]:
    """Get days until next rebalance."""
    next_date = get_next_rebalance_date(strategy)
    if next_date:
        return (next_date - date.today()).days
    return None


def get_upcoming_rebalances(days_ahead: int = 30) -> List[Dict]:
    """Get all strategies with rebalance in next N days."""
    upcoming = []
    for strategy in REBALANCE_SCHEDULE:
        days = days_until_rebalance(strategy)
        if days is not None and days <= days_ahead:
            upcoming.append({
                'strategy': strategy,
                'days_until': days,
                'date': get_next_rebalance_date(strategy).isoformat()
            })
    return sorted(upcoming, key=lambda x: x['days_until'])


def generate_monthly_report(db) -> Dict:
    """Generate monthly portfolio report."""
    from services.ranking_cache import get_cached_rankings
    from config.settings import load_strategies_config
    from models import Stock
    
    config = load_strategies_config()
    report = {
        'generated_at': datetime.now().isoformat(),
        'strategies': {},
        'upcoming_rebalances': get_upcoming_rebalances(45)
    }
    
    for strategy_name in REBALANCE_SCHEDULE:
        try:
            rankings = get_cached_rankings(db, strategy_name)
            top10 = rankings[:10] if rankings else []
            
            # Get stock names
            top10_data = []
            for i, r in enumerate(top10):
                stock = db.query(Stock).filter(Stock.ticker == r.ticker).first()
                top10_data.append({
                    'rank': i + 1,
                    'ticker': r.ticker,
                    'name': stock.name if stock else '',
                    'score': round(r.score or 0, 2)
                })
            
            report['strategies'][strategy_name] = {
                'display_name': config['strategies'].get(strategy_name, {}).get('display_name', strategy_name),
                'top10': top10_data,
                'next_rebalance': get_next_rebalance_date(strategy_name).isoformat() if get_next_rebalance_date(strategy_name) else None,
                'days_until_rebalance': days_until_rebalance(strategy_name)
            }
        except Exception as e:
            logger.error(f"Error generating report for {strategy_name}: {e}")
            report['strategies'][strategy_name] = {'error': str(e)}
    
    return report


def generate_rebalance_report(db, strategy: str, current_holdings: List[str] = None) -> Dict:
    """Generate rebalance report showing what to buy/sell."""
    from services.ranking_cache import get_cached_rankings
    from models import Stock
    
    rankings = get_cached_rankings(db, strategy)
    new_top10 = [r.ticker for r in rankings[:10]] if rankings else []
    
    if current_holdings is None:
        current_holdings = []
    
    to_sell = [t for t in current_holdings if t not in new_top10]
    to_buy = [t for t in new_top10 if t not in current_holdings]
    to_keep = [t for t in current_holdings if t in new_top10]
    
    # Build top10 with names
    top10_data = []
    for i, r in enumerate(rankings[:10]):
        stock = db.query(Stock).filter(Stock.ticker == r.ticker).first()
        top10_data.append({
            'rank': i + 1,
            'ticker': r.ticker,
            'name': stock.name if stock else ''
        })
    
    return {
        'strategy': strategy,
        'generated_at': datetime.now().isoformat(),
        'new_top10': top10_data,
        'changes': {
            'sell': to_sell,
            'buy': to_buy,
            'keep': to_keep,
            'turnover': len(to_sell) + len(to_buy)
        }
    }


def format_monthly_email(report: Dict) -> str:
    """Format monthly report as email text."""
    lines = [
        "📊 Börslabbet Monthly Report",
        f"Generated: {report['generated_at'][:10]}",
        "",
    ]
    
    # Upcoming rebalances
    if report['upcoming_rebalances']:
        lines.append("⏰ UPCOMING REBALANCES:")
        for r in report['upcoming_rebalances']:
            lines.append(f"  • {r['strategy']}: {r['days_until']} days ({r['date']})")
        lines.append("")
    
    # Strategy rankings
    for strategy, data in report['strategies'].items():
        if 'error' in data:
            continue
        lines.append(f"📈 {data.get('display_name', strategy)}")
        if data.get('days_until_rebalance') and data['days_until_rebalance'] <= 14:
            lines.append(f"   ⚠️ Rebalance in {data['days_until_rebalance']} days!")
        lines.append("   Top 10:")
        for stock in data.get('top10', []):
            lines.append(f"   {stock['rank']:2}. {stock['ticker']}: {stock['name']}")
        lines.append("")
    
    lines.append("---")
    lines.append("Log in to Börslabbet for full details and rebalancing tools.")
    
    return "\n".join(lines)


def format_rebalance_email(report: Dict, strategy_name: str) -> str:
    """Format rebalance alert as email text."""
    lines = [
        f"🔄 Rebalance Alert: {strategy_name}",
        f"Generated: {report['generated_at'][:10]}",
        "",
        "NEW TOP 10:",
    ]
    
    for stock in report['new_top10']:
        lines.append(f"  {stock['rank']:2}. {stock['ticker']}: {stock['name']}")
    
    changes = report['changes']
    if changes['turnover'] > 0:
        lines.append("")
        lines.append(f"CHANGES ({changes['turnover']} trades):")
        if changes['sell']:
            lines.append(f"  SELL: {', '.join(changes['sell'])}")
        if changes['buy']:
            lines.append(f"  BUY:  {', '.join(changes['buy'])}")
        if changes['keep']:
            lines.append(f"  KEEP: {', '.join(changes['keep'])}")
    else:
        lines.append("")
        lines.append("No changes needed - same stocks as before.")
    
    lines.append("")
    lines.append("---")
    lines.append("Log in to Börslabbet for detailed rebalancing with cost estimates.")
    
    return "\n".join(lines)


def send_report_email(to_email: str, subject: str, body: str, config: Dict) -> bool:
    """Send report email."""
    if not config.get('smtp_host') or not to_email:
        logger.warning("Email not configured")
        return False
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = config.get('smtp_from', 'reports@borslabbet.local')
        msg['To'] = to_email
        
        with smtplib.SMTP(config['smtp_host'], config.get('smtp_port', 587)) as server:
            if config.get('smtp_user'):
                server.starttls()
                server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)
        
        logger.info(f"Report email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        return False


def should_send_monthly_report() -> bool:
    """Check if today is monthly report day (1st of month)."""
    return date.today().day == 1


def should_send_rebalance_reminder(days_before: int = 7) -> List[str]:
    """Get strategies that need rebalance reminder."""
    strategies = []
    for strategy in REBALANCE_SCHEDULE:
        days = days_until_rebalance(strategy)
        if days is not None and days == days_before:
            strategies.append(strategy)
    return strategies
