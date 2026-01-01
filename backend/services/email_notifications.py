"""Email notification service for rebalancing alerts."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta
from typing import Optional
import os


def send_email(to: str, subject: str, body: str, html: Optional[str] = None) -> bool:
    """Send email via SMTP. Configure via environment variables."""
    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_pass = os.getenv('SMTP_PASS', '')
    from_email = os.getenv('FROM_EMAIL', smtp_user)
    
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
    except Exception:
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
