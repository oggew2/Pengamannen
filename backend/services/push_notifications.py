"""Web Push Notification Service using pywebpush."""
import json
import os
from datetime import datetime
from typing import Optional
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session

# VAPID keys - in production, load from environment
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', 'BKcyFC5rlpStQ2VW0_gAC5BiQWJYkHqO3vaYdCZUMQioAiKLpOz1WyhFaGwZ3PYByXeQHKmZqaPnE-uNtmSoKn8')
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', 'vF8XujXxINN9Bo3DB9ayw4qLSVuhpbsJ7aDO1i5NTxA')
VAPID_CLAIMS = {"sub": "mailto:admin@borslabbet.xyz"}


def send_push(subscription_info: dict, title: str, body: str, url: str = "/", tag: str = None) -> bool:
    """Send a push notification to a single subscription.
    
    Args:
        subscription_info: Dict with endpoint, keys.p256dh, keys.auth
        title: Notification title
        body: Notification body text
        url: URL to open on click
        tag: Optional tag to replace existing notification
    
    Returns:
        True if sent successfully, False otherwise
    """
    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "tag": tag or "borslabbet",
        "icon": "/icon-192.png",
        "badge": "/badge-72.png",
    })
    
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        return True
    except WebPushException as e:
        print(f"Push failed: {e}")
        # 410 Gone = subscription expired
        if e.response and e.response.status_code == 410:
            return False  # Caller should delete subscription
        return False


def send_to_user(db: Session, user_id: int, title: str, body: str, url: str = "/") -> int:
    """Send notification to all subscriptions for a user.
    
    Returns number of successful sends.
    """
    from models import PushSubscription
    
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    sent = 0
    expired = []
    
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
        }
        if send_push(subscription_info, title, body, url):
            sub.last_used = datetime.utcnow()
            sent += 1
        else:
            expired.append(sub.id)
    
    # Clean up expired subscriptions
    if expired:
        db.query(PushSubscription).filter(PushSubscription.id.in_(expired)).delete(synchronize_session=False)
    
    db.commit()
    return sent


def send_to_all(db: Session, title: str, body: str, url: str = "/") -> int:
    """Send notification to all subscriptions (broadcast).
    
    Returns number of successful sends.
    """
    from models import PushSubscription
    
    subs = db.query(PushSubscription).all()
    sent = 0
    expired = []
    
    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth}
        }
        if send_push(subscription_info, title, body, url):
            sub.last_used = datetime.utcnow()
            sent += 1
        else:
            expired.append(sub.id)
    
    # Clean up expired subscriptions
    if expired:
        db.query(PushSubscription).filter(PushSubscription.id.in_(expired)).delete(synchronize_session=False)
    
    db.commit()
    return sent


# Notification templates
def notify_rebalance_reminder(db: Session, days_until: int) -> int:
    """Send rebalance reminder to all users."""
    if days_until == 3:
        title = "📅 Ombalansering om 3 dagar"
        body = "Dags att förbereda din kvartalsombalansering"
    elif days_until == 1:
        title = "⏰ Ombalansering imorgon!"
        body = "Glöm inte att ombalansera din portfölj"
    elif days_until == 0:
        title = "🔔 Dags att ombalansera!"
        body = "Idag är det ombalanseringsdag - kolla din portfölj"
    else:
        return 0
    
    return send_to_all(db, title, body, "/dashboard")


def notify_ranking_change(db: Session, user_id: int, ticker: str, old_rank: int, new_rank: int) -> int:
    """Notify user when their stock's rank changes significantly."""
    if new_rank > 20 and old_rank <= 20:
        title = f"⚠️ {ticker} föll ur topp 20"
        body = f"{ticker} är nu rank {new_rank} - överväg att sälja"
    elif new_rank <= 10 and old_rank > 10:
        title = f"📈 {ticker} gick in i topp 10"
        body = f"{ticker} är nu rank {new_rank}"
    else:
        return 0
    
    return send_to_user(db, user_id, title, body, "/dashboard")


def notify_weekly_digest(db: Session, user_id: int, week_return: float, portfolio_value: float) -> int:
    """Send weekly portfolio summary."""
    sign = "+" if week_return >= 0 else ""
    title = "📊 Veckosammanfattning"
    body = f"Din portfölj: {sign}{week_return:.1f}% denna vecka ({portfolio_value:,.0f} kr)"
    return send_to_user(db, user_id, title, body, "/dashboard")
