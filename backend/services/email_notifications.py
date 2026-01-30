"""Email notification service for rebalancing alerts."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent.parent / ".env")


def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    """Send email via SMTP. Configure via environment variables."""
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASSWORD', '')  # Match .env variable name
    from_email = os.getenv('SMTP_FROM', smtp_user)
    
    if not smtp_user or not smtp_pass:
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to
    
    msg.attach(MIMEText(body, 'plain'))
    if html:
        msg.attach(MIMEText(html, 'html'))
    
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_rebalance_reminder(to: str, strategy: str, rebalance_date: date, stocks: list[str]) -> bool:
    """Send rebalance reminder email."""
    days_until = (rebalance_date - date.today()).days
    
    subject = f"Börslabbet: {strategy} rebalansering om {days_until} dagar"
    
    body = f"""Hej!

Din {strategy}-strategi ska rebalanseras {rebalance_date.strftime('%Y-%m-%d')} ({days_until} dagar kvar).

Nuvarande topp 10:
{chr(10).join(f'  {i+1}. {s}' for i, s in enumerate(stocks[:10]))}

Logga in på Börslabbet-appen för att se köp/sälj-lista och kostnadsuppskattning.

Lycka till med investeringarna!
"""
    
    html = f"""
<h2>Rebalansering: {strategy}</h2>
<p>Din strategi ska rebalanseras <strong>{rebalance_date.strftime('%Y-%m-%d')}</strong> ({days_until} dagar kvar).</p>
<h3>Nuvarande topp 10:</h3>
<ol>{''.join(f'<li>{s}</li>' for s in stocks[:10])}</ol>
<p><a href="http://localhost:5173/portfolio/my">Öppna appen för köp/sälj-lista →</a></p>
"""
    
    return send_email(to, subject, body, html)


def get_upcoming_rebalances(days_ahead: int = 14) -> list[dict]:
    """Get strategies with rebalances in the next N days."""
    from config.settings import load_strategies_config
    from services.portfolio import get_next_rebalance_dates
    
    upcoming = []
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    
    config = load_strategies_config()
    dates = get_next_rebalance_dates(config)
    for strategy, rebal_date in dates.items():
        if today <= rebal_date <= cutoff:
            upcoming.append({
                'strategy': strategy,
                'date': rebal_date,
                'days_until': (rebal_date - today).days
            })
    
    return upcoming


def check_portfolio_alerts(db) -> list[dict]:
    """Check all user portfolios for stocks that dropped below rank 20.
    
    Returns list of alerts to send.
    """
    from models import User, UserPortfolio
    from services.ranking_cache import compute_nordic_momentum
    import json
    
    # Get current rankings
    result = compute_nordic_momentum()
    if 'error' in result:
        return []
    
    rank_map = {r['ticker']: r for r in result['rankings']}
    
    alerts = []
    
    # Get all users with portfolios
    users = db.query(User).filter(User.is_active == True).all()
    
    for user in users:
        if not user.email:
            continue
            
        portfolios = db.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id
        ).all()
        
        user_alerts = []
        for portfolio in portfolios:
            if not portfolio.holdings:
                continue
            
            try:
                holdings = json.loads(portfolio.holdings)
            except:
                continue
            
            for holding in holdings:
                ticker = holding.get('ticker')
                if not ticker:
                    continue
                
                ranking = rank_map.get(ticker)
                if ranking and ranking['rank'] > 20:
                    user_alerts.append({
                        'ticker': ticker,
                        'name': ranking.get('name', ticker),
                        'rank': ranking['rank'],
                        'momentum': ranking['momentum'],
                        'portfolio': portfolio.name
                    })
        
        if user_alerts:
            # Get top replacement candidates
            replacements = [r for r in result['rankings'][:10] 
                          if r['ticker'] not in [a['ticker'] for a in user_alerts]][:3]
            
            alerts.append({
                'user': user,
                'alerts': user_alerts,
                'replacements': replacements
            })
    
    return alerts


def send_portfolio_alert_email(user, alerts: list[dict], replacements: list[dict]) -> bool:
    """Send monthly portfolio alert email to user with professional HTML design."""
    subject = "⚠️ Börslabbet: Aktier under rank 20"
    
    # Plain text version
    alert_lines = []
    for a in alerts:
        alert_lines.append(f"  • {a['ticker']} ({a['name'][:20]}): Rank {a['rank']}, Momentum {a['momentum']:.1f}%")
    
    replacement_lines = []
    for r in replacements:
        replacement_lines.append(f"  • {r['ticker']} ({r['name'][:20]}): Rank {r['rank']}, Momentum {r['momentum']:.1f}%")
    
    body = f"""Hej {user.name or 'investerare'}!

Följande aktier i din portfölj har fallit under rank 20 i Nordic Sammansatt Momentum:

{chr(10).join(alert_lines)}

Enligt banding-reglerna bör dessa säljas och ersättas med aktier från topp 10.

Förslag på ersättare:
{chr(10).join(replacement_lines)}

Logga in på Börslabbet-appen för fullständig lista och köp/sälj-rekommendationer.

Lycka till!
Börslabbet
"""

    # Professional HTML version with inline styles (email best practice)
    alert_rows = ''.join(f'''
        <tr>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #1f2937;">{a['ticker']}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #6b7280;">{a['name'][:25]}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #dc2626; text-align: center; font-weight: bold;">{a['rank']}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #1f2937; text-align: right;">{a['momentum']:.1f}%</td>
        </tr>
    ''' for a in alerts)
    
    replacement_rows = ''.join(f'''
        <tr>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #1f2937;">{r['ticker']}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #6b7280;">{r['name'][:25]}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #059669; text-align: center; font-weight: bold;">{r['rank']}</td>
            <td style="padding: 12px 16px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 14px; color: #1f2937; text-align: right;">{r['momentum']:.1f}%</td>
        </tr>
    ''' for r in replacements)

    html = f'''<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Börslabbet Portfolio Alert</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: Arial, sans-serif;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Main Container -->
                <table width="600" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); background-color: #1e40af; padding: 32px 40px; border-radius: 8px 8px 0 0;">
                            <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td>
                                        <h1 style="margin: 0; font-family: Arial, sans-serif; font-size: 24px; font-weight: bold; color: #ffffff;">⚠️ Portfolio Alert</h1>
                                        <p style="margin: 8px 0 0 0; font-family: Arial, sans-serif; font-size: 14px; color: #bfdbfe;">Nordic Sammansatt Momentum</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Greeting -->
                    <tr>
                        <td style="padding: 32px 40px 24px 40px;">
                            <p style="margin: 0; font-family: Arial, sans-serif; font-size: 16px; color: #374151; line-height: 1.6;">
                                Hej {user.name or 'investerare'}!
                            </p>
                            <p style="margin: 16px 0 0 0; font-family: Arial, sans-serif; font-size: 16px; color: #374151; line-height: 1.6;">
                                Följande aktier i din portfölj har fallit under <strong>rank 20</strong> och bör enligt banding-reglerna säljas:
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Alert Table -->
                    <tr>
                        <td style="padding: 0 40px 24px 40px;">
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
                                <tr style="background-color: #fef2f2;">
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #991b1b; text-transform: uppercase;">Ticker</td>
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #991b1b; text-transform: uppercase;">Namn</td>
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #991b1b; text-transform: uppercase; text-align: center;">Rank</td>
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #991b1b; text-transform: uppercase; text-align: right;">Momentum</td>
                                </tr>
                                {alert_rows}
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Replacement Section -->
                    <tr>
                        <td style="padding: 0 40px 24px 40px;">
                            <p style="margin: 0 0 16px 0; font-family: Arial, sans-serif; font-size: 16px; color: #374151; line-height: 1.6;">
                                <strong>Förslag på ersättare</strong> från topp 10:
                            </p>
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
                                <tr style="background-color: #ecfdf5;">
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #065f46; text-transform: uppercase;">Ticker</td>
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #065f46; text-transform: uppercase;">Namn</td>
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #065f46; text-transform: uppercase; text-align: center;">Rank</td>
                                    <td style="padding: 12px 16px; font-family: Arial, sans-serif; font-size: 12px; font-weight: bold; color: #065f46; text-transform: uppercase; text-align: right;">Momentum</td>
                                </tr>
                                {replacement_rows}
                            </table>
                        </td>
                    </tr>
                    
                    <!-- CTA Button -->
                    <tr>
                        <td align="center" style="padding: 8px 40px 32px 40px;">
                            <table border="0" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td style="background-color: #2563eb; border-radius: 6px;">
                                        <a href="https://app.borslabbet.se/portfolio/my" style="display: inline-block; padding: 14px 32px; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; color: #ffffff; text-decoration: none;">
                                            Öppna portföljen →
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 24px 40px; border-radius: 0 0 8px 8px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; font-family: Arial, sans-serif; font-size: 12px; color: #6b7280; line-height: 1.6; text-align: center;">
                                Du får detta mail för att du har aktier i din Börslabbet-portfölj.<br>
                                <a href="https://app.borslabbet.se/settings" style="color: #2563eb; text-decoration: none;">Hantera notifikationer</a>
                            </p>
                            <p style="margin: 16px 0 0 0; font-family: Arial, sans-serif; font-size: 11px; color: #9ca3af; text-align: center;">
                                © Börslabbet AB · Stockholm, Sverige
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''
    
    return send_email(user.email, subject, body, html)


def send_monthly_portfolio_alerts(db) -> dict:
    """Check and send portfolio alerts to all users. Run on 1st of month."""
    alerts = check_portfolio_alerts(db)
    
    sent = 0
    failed = 0
    
    for alert in alerts:
        if send_portfolio_alert_email(alert['user'], alert['alerts'], alert['replacements']):
            sent += 1
        else:
            failed += 1
    
    return {'sent': sent, 'failed': failed, 'total_alerts': len(alerts)}


def generate_monthly_rankings_email(db) -> dict:
    """Generate monthly rankings email for all real users (excludes test accounts)."""
    from models import User
    from services.ranking_cache import compute_nordic_momentum
    
    result = compute_nordic_momentum()
    if 'error' in result:
        return {'sent': 0, 'failed': 0, 'error': result['error']}
    
    rankings = result['rankings']
    
    # Only real users - exclude @test.com addresses
    users = db.query(User).filter(
        User.is_active == True, 
        User.email != None,
        ~User.email.like('%@test.com')
    ).all()
    
    sent = 0
    failed = 0
    
    for user in users:
        if send_monthly_rankings_email_to_user(user, rankings, set(), [], []):
            sent += 1
        else:
            failed += 1
    
    return {'sent': sent, 'failed': failed}


def send_monthly_rankings_email_to_user(user, rankings: list, holdings: set, sells: list, buys: list) -> bool:
    """Send monthly rankings email to a single user."""
    today = date.today()
    month_name = ['januari', 'februari', 'mars', 'april', 'maj', 'juni', 
                  'juli', 'augusti', 'september', 'oktober', 'november', 'december'][today.month - 1]
    
    has_rebalance = len(sells) > 0
    subject = f"📊 Börslabbet {month_name.capitalize()}: Nordic Momentum Top 40" + (" ⚠️ Rebalansering!" if has_rebalance else "")
    
    # Plain text
    body = f"""Hej {user.name or 'investerare'}!

Här är månadens Nordic Sammansatt Momentum-ranking för {month_name} {today.year}.

TOP 10:
{chr(10).join(f'{r["rank"]:2}. {r["ticker"]:12} {r["momentum"]:.1f}%' for r in rankings[:10])}

"""
    if has_rebalance:
        body += f"""
⚠️ REBALANSERING KRÄVS:
Sälj: {', '.join(s['ticker'] for s in sells)}
Köp: {', '.join(b['ticker'] for b in buys)}
"""
    
    body += f"""
Se fullständig lista på https://borslabbet.xyz

Lycka till!
Börslabbet
"""

    # Build HTML rows for top 40
    def make_row(r, in_portfolio):
        bg = '#fef3c7' if in_portfolio else ('#f0fdf4' if r['rank'] <= 10 else '#ffffff')
        badge = ' 📌' if in_portfolio else ''
        return f'''<tr style="background-color: {bg};">
            <td style="padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 13px; color: #374151; text-align: center;">{r['rank']}</td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 13px; color: #1f2937; font-weight: {'bold' if r['rank'] <= 10 else 'normal'};">{r['ticker']}{badge}</td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 12px; color: #6b7280;">{r['name'][:22]}</td>
            <td style="padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-family: Arial, sans-serif; font-size: 13px; color: #059669; text-align: right; font-weight: bold;">{r['momentum']:.1f}%</td>
        </tr>'''
    
    ranking_rows = ''.join(make_row(r, r['ticker'] in holdings) for r in rankings[:40])
    
    # Rebalance section
    rebalance_html = ''
    if has_rebalance:
        sell_rows = ''.join(f'''<tr>
            <td style="padding: 10px 16px; border-bottom: 1px solid #fecaca; font-family: Arial, sans-serif; font-size: 14px; color: #dc2626; font-weight: bold;">SÄLJ</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #fecaca; font-family: Arial, sans-serif; font-size: 14px; color: #1f2937;">{s['ticker']}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #fecaca; font-family: Arial, sans-serif; font-size: 14px; color: #6b7280;">Rank {s['rank']}</td>
        </tr>''' for s in sells)
        
        buy_rows = ''.join(f'''<tr>
            <td style="padding: 10px 16px; border-bottom: 1px solid #bbf7d0; font-family: Arial, sans-serif; font-size: 14px; color: #059669; font-weight: bold;">KÖP</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #bbf7d0; font-family: Arial, sans-serif; font-size: 14px; color: #1f2937;">{b['ticker']}</td>
            <td style="padding: 10px 16px; border-bottom: 1px solid #bbf7d0; font-family: Arial, sans-serif; font-size: 14px; color: #6b7280;">Rank {b['rank']}</td>
        </tr>''' for b in buys)
        
        rebalance_html = f'''
        <tr>
            <td style="padding: 24px 40px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #fef2f2; border: 2px solid #dc2626; border-radius: 8px; overflow: hidden;">
                    <tr>
                        <td style="padding: 16px 20px; background-color: #dc2626;">
                            <h3 style="margin: 0; font-family: Arial, sans-serif; font-size: 16px; color: #ffffff;">⚠️ Rebalansering krävs!</h3>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 16px;">
                            <table width="100%" border="0" cellspacing="0" cellpadding="0">
                                {sell_rows}
                                {buy_rows}
                            </table>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>'''

    html = f'''<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0">
        <tr>
            <td align="center" style="padding: 32px 16px;">
                <table width="640" border="0" cellspacing="0" cellpadding="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 28px 40px; border-radius: 12px 12px 0 0;">
                            <h1 style="margin: 0; font-family: Arial, sans-serif; font-size: 22px; color: #ffffff;">📊 Nordic Momentum</h1>
                            <p style="margin: 6px 0 0 0; font-family: Arial, sans-serif; font-size: 14px; color: #bfdbfe;">{month_name.capitalize()} {today.year} • Månadsrapport</p>
                        </td>
                    </tr>
                    
                    <!-- Greeting -->
                    <tr>
                        <td style="padding: 28px 40px 20px 40px;">
                            <p style="margin: 0; font-family: Arial, sans-serif; font-size: 15px; color: #374151; line-height: 1.5;">
                                Hej {user.name or 'investerare'}! Här är månadens ranking för Nordic Sammansatt Momentum.
                                {'<br><br><strong style="color: #dc2626;">⚠️ Du har aktier som fallit under rank 20 - se rebalansering nedan!</strong>' if has_rebalance else ''}
                            </p>
                        </td>
                    </tr>
                    
                    {rebalance_html}
                    
                    <!-- Rankings Table -->
                    <tr>
                        <td style="padding: 16px 40px 28px 40px;">
                            <h3 style="margin: 0 0 12px 0; font-family: Arial, sans-serif; font-size: 15px; color: #1f2937;">Top 40 Ranking</h3>
                            <p style="margin: 0 0 12px 0; font-family: Arial, sans-serif; font-size: 12px; color: #6b7280;">📌 = Din aktie • Grönt = Topp 10 • Gult = I din portfölj</p>
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
                                <tr style="background-color: #1e3a8a;">
                                    <td style="padding: 10px 12px; font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase; text-align: center; width: 50px;">#</td>
                                    <td style="padding: 10px 12px; font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase;">Ticker</td>
                                    <td style="padding: 10px 12px; font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase;">Namn</td>
                                    <td style="padding: 10px 12px; font-family: Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase; text-align: right;">Mom.</td>
                                </tr>
                                {ranking_rows}
                            </table>
                        </td>
                    </tr>
                    
                    <!-- CTA -->
                    <tr>
                        <td align="center" style="padding: 0 40px 28px 40px;">
                            <table border="0" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td style="background-color: #2563eb; border-radius: 6px;">
                                        <a href="https://borslabbet.xyz" style="display: inline-block; padding: 14px 28px; font-family: Arial, sans-serif; font-size: 15px; font-weight: bold; color: #ffffff; text-decoration: none;">
                                            Öppna Börslabbet →
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 20px 40px; border-radius: 0 0 12px 12px; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; font-family: Arial, sans-serif; font-size: 11px; color: #6b7280; text-align: center; line-height: 1.5;">
                                <a href="https://borslabbet.xyz" style="color: #2563eb; text-decoration: none; font-weight: bold;">borslabbet.xyz</a><br>
                                © Börslabbet AB • Stockholm
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>'''
    
    return send_email(user.email, subject, body, html)
