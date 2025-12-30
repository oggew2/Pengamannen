"""
APScheduler jobs for automatic data fetching.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import get_settings
from db import SessionLocal
from services.optimized_yfinance import optimized_sync_with_guarantee

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

def sync_job(full_refresh: bool = False):
    """Job to sync stock data from EODHD."""
    settings = get_settings()
    if not settings.eodhd_api_key:
        logger.warning("EODHD_API_KEY not configured, skipping sync")
        return
    
    logger.info(f"Starting scheduled sync (full_refresh={full_refresh})")
    db = SessionLocal()
    try:
        result = optimized_sync_with_guarantee(db, region="sweden", market_cap="large")
        logger.info(f"Sync complete: {result}")
    except Exception as e:
        logger.error(f"Sync failed: {e}")
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
        replace_existing=True,
        kwargs={"full_refresh": False}
    )
    
    # Weekly full refresh on Friday at configured hour
    scheduler.add_job(
        sync_job,
        CronTrigger(day_of_week="fri", hour=settings.data_sync_hour, minute=30),
        id="weekly_full_sync",
        replace_existing=True,
        kwargs={"full_refresh": True}
    )
    
    scheduler.start()
    logger.info(f"Scheduler started: daily sync at {settings.data_sync_hour}:00 UTC, weekly full refresh on Fridays")

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
