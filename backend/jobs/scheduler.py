"""
APScheduler jobs for automatic data fetching.
"""
import logging
import asyncio
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings
from db import SessionLocal

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# Track retry state
_sync_retry_count = 0
_MAX_RETRIES = 2


def sync_job(is_retry: bool = False):
    """Job to sync all stock data (fundamentals + prices) using Avanza."""
    global _sync_retry_count
    
    if is_retry:
        logger.info(f"Starting RETRY sync (attempt {_sync_retry_count + 1}/{_MAX_RETRIES})")
    else:
        logger.info("Starting scheduled Avanza sync")
        _sync_retry_count = 0  # Reset retry count for new scheduled sync
    
    db = SessionLocal()
    sync_success = False
    
    try:
        from services.avanza_fetcher_v2 import avanza_sync
        from services.stock_validator import mark_stocks_with_fundamentals_active
        from services.alerting import (
            check_and_create_alerts, resolve_old_alerts, 
            send_alert_email, get_unnotified_critical_alerts, mark_alerts_notified
        )
        from config.settings import get_settings
        
        result = asyncio.run(avanza_sync(db, region="sweden", market_cap="large"))
        logger.info(f"Sync complete: {result}")
        sync_success = True
        _sync_retry_count = 0  # Reset on success
        
        # Clear backtest cache - results are stale after new data
        from models import BacktestResult
        deleted = db.query(BacktestResult).delete()
        db.commit()
        logger.info(f"Cleared {deleted} cached backtest results")
        
        # Update is_active flag based on which stocks have fundamentals
        active_result = mark_stocks_with_fundamentals_active(db)
        if active_result.get('success'):
            logger.info(f"Updated is_active: {active_result['updated']} stocks")
        else:
            logger.error(f"is_active update failed: {active_result.get('error')}")
        
        # Check data integrity and create alerts if issues found
        alert_result = check_and_create_alerts(db)
        if alert_result['alerts_created']:
            logger.warning(f"Data alerts created: {alert_result['alerts_created']}")
            
            # Send email for critical alerts
            settings = get_settings()
            if settings.alert_email:
                unnotified = get_unnotified_critical_alerts(db)
                if unnotified:
                    email_config = {
                        'alert_email': settings.alert_email,
                        'smtp_host': settings.smtp_host,
                        'smtp_port': settings.smtp_port,
                        'smtp_user': settings.smtp_user,
                        'smtp_password': settings.smtp_password,
                        'smtp_from': settings.smtp_from
                    }
                    if send_alert_email(unnotified, email_config):
                        mark_alerts_notified(db, [a['id'] for a in unnotified])
        else:
            # No issues - resolve any old alerts
            resolve_old_alerts(db)
            
        # CRITICAL FIX: Force memory cleanup after sync
        import gc
        gc.collect()
        logger.info("Memory cleanup completed after sync")
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sync_success = False
        
        # Schedule retry if not already a retry and under max retries
        if _sync_retry_count < _MAX_RETRIES:
            _sync_retry_count += 1
            retry_hour = get_settings().data_sync_hour + _sync_retry_count
            logger.warning(f"Scheduling retry #{_sync_retry_count} at hour {retry_hour}")
            
            # Schedule one-time retry job
            scheduler.add_job(
                lambda: sync_job(is_retry=True),
                CronTrigger(hour=retry_hour, minute=0),
                id=f"sync_retry_{_sync_retry_count}",
                replace_existing=True,
                max_instances=1
            )
        else:
            # All retries exhausted - send critical alert
            logger.critical(f"All sync retries exhausted. Sending alert.")
            try:
                settings = get_settings()
                if settings.alert_email:
                    from services.alerting import send_alert_email
                    send_alert_email(
                        [{'severity': 'CRITICAL', 'message': f'Data sync failed after {_MAX_RETRIES} retries: {e}'}],
                        {
                            'alert_email': settings.alert_email,
                            'smtp_host': settings.smtp_host,
                            'smtp_port': settings.smtp_port,
                            'smtp_user': settings.smtp_user,
                            'smtp_password': settings.smtp_password,
                            'smtp_from': settings.smtp_from
                        }
                    )
            except Exception as alert_err:
                logger.error(f"Failed to send sync failure alert: {alert_err}")
    finally:
        # CRITICAL FIX: Ensure database session is properly closed
        try:
            db.close()
        except Exception:
            pass
        
        # Additional cleanup
        import gc
        gc.collect()

def scan_new_stocks_job():
    """Job to scan for new stocks - runs every 2 weeks at night.
    
    Also reclassifies existing stocks and runs a discovery sync
    to find fundamentals for newly discovered stocks.
    """
    logger.info("Starting scheduled stock scan for new listings")
    db = SessionLocal()
    try:
        from services.stock_scanner import scan_for_new_stocks, classify_stock_type
        import sqlite3
        
        conn = sqlite3.connect('app.db')
        cur = conn.cursor()
        
        # Step 1: Reclassify existing stocks (fast - just DB update)
        logger.info("Reclassifying existing stocks...")
        cur.execute("SELECT ticker, name FROM stocks WHERE stock_type = 'stock'")
        stocks = cur.fetchall()
        reclassified = 0
        for ticker, name in stocks:
            new_type = classify_stock_type(ticker, name or '')
            if new_type != 'stock':
                cur.execute("UPDATE stocks SET stock_type = ? WHERE ticker = ?", (new_type, ticker))
                reclassified += 1
        conn.commit()
        logger.info(f"Reclassified {reclassified} stocks")
        
        # Step 2: Scan for new stocks (incremental - new IDs only)
        cur.execute('SELECT MAX(CAST(avanza_id AS INTEGER)) FROM stocks WHERE avanza_id IS NOT NULL')
        current_max = cur.fetchone()[0] or 2250000
        conn.close()
        
        start_id = current_max + 1
        end_id = current_max + 500000
        
        logger.info(f"Scanning new ID range: {start_id} - {end_id}")
        result = scan_for_new_stocks(
            ranges=[{"start": start_id, "end": end_id}],
            max_workers=10
        )
        logger.info(f"Stock scan complete: {result['new_stocks_found']} new stocks found")
        
        # Step 3: Discovery sync - try to get fundamentals for inactive stocks
        # This runs less frequently than daily sync but covers all stocks
        logger.info("Running discovery sync for inactive stocks...")
        from services.avanza_fetcher_v2 import avanza_sync
        from services.stock_validator import mark_stocks_with_fundamentals_active
        
        # Pass tier='discovery' to sync all stocks, not just active ones
        discovery_result = asyncio.run(avanza_sync(db, region="sweden", market_cap="large", tier='discovery'))
        logger.info(f"Discovery sync complete: {discovery_result}")
        
        # Update is_active based on which stocks now have fundamentals
        active_result = mark_stocks_with_fundamentals_active(db)
        if active_result.get('success'):
            logger.info(f"Updated is_active: {active_result['updated']} stocks now active")
        
    except Exception as e:
        logger.error(f"Stock scan failed: {e}")
    finally:
        db.close()

def send_reports_job():
    """Job to send email reports - runs daily, sends based on schedule."""
    logger.info("Checking for reports to send")
    db = SessionLocal()
    try:
        from services.email_reports import (
            should_send_monthly_report, should_send_rebalance_reminder,
            generate_monthly_report, generate_rebalance_report,
            format_monthly_email, format_rebalance_email, send_report_email
        )
        from config.settings import get_settings
        
        settings = get_settings()
        if not settings.alert_email:
            logger.info("No alert_email configured, skipping reports")
            return
        
        email_config = {
            'smtp_host': settings.smtp_host,
            'smtp_port': settings.smtp_port,
            'smtp_user': settings.smtp_user,
            'smtp_password': settings.smtp_password,
            'smtp_from': settings.smtp_from
        }
        
        # Monthly report on 1st of month
        if should_send_monthly_report():
            logger.info("Sending monthly report")
            report = generate_monthly_report(db)
            body = format_monthly_email(report)
            send_report_email(settings.alert_email, "📊 Börslabbet Monthly Report", body, email_config)
        
        # Rebalance reminders 7 days before
        strategies = should_send_rebalance_reminder(days_before=7)
        for strategy in strategies:
            logger.info(f"Sending rebalance reminder for {strategy}")
            report = generate_rebalance_report(db, strategy)
            body = format_rebalance_email(report, strategy)
            send_report_email(settings.alert_email, f"🔄 Rebalance in 7 days: {strategy}", body, email_config)
        
        # Rebalance day reminder
        strategies = should_send_rebalance_reminder(days_before=0)
        for strategy in strategies:
            logger.info(f"Sending rebalance day alert for {strategy}")
            report = generate_rebalance_report(db, strategy)
            body = format_rebalance_email(report, strategy)
            send_report_email(settings.alert_email, f"🔄 REBALANCE TODAY: {strategy}", body, email_config)
            
    except Exception as e:
        logger.error(f"Report job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Start the APScheduler with configured jobs."""
    settings = get_settings()
    
    if not settings.data_sync_enabled:
        logger.info("Data sync disabled, scheduler not started")
        return
    
    # Daily sync at configured hour (UTC)
    scheduler.add_job(
        sync_job,
        CronTrigger(hour=settings.data_sync_hour, minute=0),
        id="daily_sync",
        replace_existing=True
    )
    
    # Bi-weekly stock scan for new listings (every other Sunday at 3 AM UTC)
    scheduler.add_job(
        scan_new_stocks_job,
        CronTrigger(day_of_week="sun", hour=3, minute=0, week="*/2"),
        id="biweekly_stock_scan",
        replace_existing=True
    )
    
    # Daily report check at 8 AM UTC (sends monthly/rebalance emails as needed)
    scheduler.add_job(
        send_reports_job,
        CronTrigger(hour=8, minute=0),
        id="daily_reports",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started: sync at {settings.data_sync_hour}:00, reports at 08:00 UTC")

def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

def get_scheduler_status() -> dict:
    """Get current scheduler status."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        })
    return {
        "running": scheduler.running,
        "jobs": jobs
    }
