"""Alerting service - creates alerts from integrity checks and sends notifications."""
import logging
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def check_and_create_alerts(db) -> Dict:
    """Run integrity checks and create alerts for any issues found."""
    from services.data_integrity import DataIntegrityChecker
    from models import DataAlert
    
    checker = DataIntegrityChecker(db)
    result = checker.run_all_checks()
    
    alerts_created = []
    
    # Create alerts for critical issues
    for issue in result.get('issues', []):
        alert = DataAlert(
            severity='CRITICAL',
            alert_type=issue.get('type', 'UNKNOWN'),
            message=issue.get('message', ''),
            details_json=json.dumps(issue)
        )
        db.add(alert)
        alerts_created.append({'severity': 'CRITICAL', 'type': issue.get('type')})
    
    # Create alerts for warnings
    for warning in result.get('warnings', []):
        alert = DataAlert(
            severity='WARNING',
            alert_type=warning.get('type', 'UNKNOWN'),
            message=warning.get('message', ''),
            details_json=json.dumps(warning)
        )
        db.add(alert)
        alerts_created.append({'severity': 'WARNING', 'type': warning.get('type')})
    
    if alerts_created:
        db.commit()
        logger.info(f"Created {len(alerts_created)} alerts")
    
    return {
        'status': result['status'],
        'alerts_created': alerts_created,
        'safe_to_trade': result['safe_to_trade']
    }


def send_alert_email(alerts: List[Dict], config: Dict) -> bool:
    """Send email notification for critical alerts."""
    if not config.get('smtp_host') or not config.get('alert_email'):
        logger.warning("Email not configured, skipping notification")
        return False
    
    critical = [a for a in alerts if a.get('severity') == 'CRITICAL']
    if not critical:
        return False
    
    subject = f"🚨 Börslabbet: {len(critical)} Critical Data Alert(s)"
    body = "Critical data integrity issues detected:\n\n"
    for alert in critical:
        body += f"• {alert.get('type')}: {alert.get('message', '')}\n"
    body += f"\nTimestamp: {datetime.now().isoformat()}"
    body += "\n\nPlease check the data management page for details."
    
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = config.get('smtp_from', 'alerts@borslabbet.local')
        msg['To'] = config['alert_email']
        
        with smtplib.SMTP(config['smtp_host'], config.get('smtp_port', 587)) as server:
            if config.get('smtp_user'):
                server.starttls()
                server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)
        
        logger.info(f"Alert email sent to {config['alert_email']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
        return False


def mark_alerts_notified(db, alert_ids: List[int]):
    """Mark alerts as notified after email sent."""
    from models import DataAlert
    db.query(DataAlert).filter(DataAlert.id.in_(alert_ids)).update(
        {DataAlert.notified: True}, synchronize_session=False
    )
    db.commit()


def resolve_old_alerts(db):
    """Auto-resolve alerts older than 24h if current status is OK."""
    from services.data_integrity import DataIntegrityChecker
    from models import DataAlert
    from datetime import timedelta
    
    checker = DataIntegrityChecker(db)
    result = checker.run_all_checks()
    
    if result['status'] == 'OK':
        # Resolve all unresolved alerts
        now = datetime.now()
        updated = db.query(DataAlert).filter(
            DataAlert.resolved == False
        ).update({
            DataAlert.resolved: True,
            DataAlert.resolved_at: now
        }, synchronize_session=False)
        db.commit()
        if updated:
            logger.info(f"Auto-resolved {updated} alerts")
        return updated
    return 0


def get_alert_history(db, limit: int = 50, include_resolved: bool = False) -> List[Dict]:
    """Get recent alert history."""
    from models import DataAlert
    
    query = db.query(DataAlert).order_by(DataAlert.timestamp.desc())
    if not include_resolved:
        query = query.filter(DataAlert.resolved == False)
    
    alerts = query.limit(limit).all()
    
    return [{
        'id': a.id,
        'timestamp': a.timestamp.isoformat() if a.timestamp else None,
        'severity': a.severity,
        'alert_type': a.alert_type,
        'message': a.message,
        'resolved': a.resolved,
        'resolved_at': a.resolved_at.isoformat() if a.resolved_at else None,
        'notified': a.notified
    } for a in alerts]


def get_unnotified_critical_alerts(db) -> List[Dict]:
    """Get critical alerts that haven't been emailed yet."""
    from models import DataAlert
    
    alerts = db.query(DataAlert).filter(
        DataAlert.severity == 'CRITICAL',
        DataAlert.notified == False,
        DataAlert.resolved == False
    ).all()
    
    return [{
        'id': a.id,
        'type': a.alert_type,
        'message': a.message,
        'severity': a.severity
    } for a in alerts]
