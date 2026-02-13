"""
APScheduler jobs for automatic data fetching.
"""
import logging
import asyncio
import os
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

# Data source: 'tradingview' or 'avanza'
DATA_SOURCE = os.getenv('DATA_SOURCE', 'tradingview')


async def tradingview_sync(db, force_refresh: bool = False) -> dict:
    """
    Sync fundamentals from TradingView Scanner API.
    Much faster than Avanza (~1s vs ~51s).
    Saves weekly snapshots for historical backtesting.
    """
    from services.tradingview_fetcher import TradingViewFetcher
    from services.ticker_mapping import tv_to_db_ticker
    from models import Fundamentals, Stock, FundamentalsSnapshot
    from datetime import date, timedelta
    import time
    
    start_time = time.time()
    fetcher = TradingViewFetcher()
    today = date.today()
    
    try:
        stocks = fetcher.fetch_all(min_market_cap=2e9)
        
        if not stocks:
            logger.error("TradingView returned no data")
            return {"status": "ERROR", "message": "No data from TradingView"}
        
        # Get existing tickers for matching
        existing_stocks = {s.ticker: s for s in db.query(Stock).all()}
        
        # Check if we should save a snapshot (weekly for historical backtesting)
        week_start = today - timedelta(days=today.weekday())
        existing_snapshot = db.query(FundamentalsSnapshot).filter(
            FundamentalsSnapshot.snapshot_date >= week_start
        ).first()
        save_snapshot = existing_snapshot is None
        
        updated = 0
        snapshots_saved = 0
        for stock_data in stocks:
            db_ticker = stock_data['db_ticker']
            
            # Update or create fundamentals record
            fund = db.query(Fundamentals).filter(
                Fundamentals.ticker == db_ticker,
                Fundamentals.data_source == 'tradingview'
            ).first()
            
            if not fund:
                fund = Fundamentals(ticker=db_ticker)
                db.add(fund)
            
            # Update all fields
            fund.market_cap = stock_data.get('market_cap')
            fund.pe = stock_data.get('pe')
            fund.pb = stock_data.get('pb')
            fund.ps = stock_data.get('ps')
            fund.p_fcf = stock_data.get('p_fcf')
            fund.ev_ebitda = stock_data.get('ev_ebitda')
            fund.roe = stock_data.get('roe')
            fund.roa = stock_data.get('roa')
            fund.roic = stock_data.get('roic')
            fund.fcfroe = stock_data.get('fcfroe')
            fund.dividend_yield = stock_data.get('dividend_yield')
            fund.net_income = stock_data.get('net_income')
            fund.operating_cf = stock_data.get('operating_cf')
            fund.total_assets = stock_data.get('total_assets')
            fund.long_term_debt = stock_data.get('long_term_debt')
            fund.current_ratio = stock_data.get('current_ratio')
            fund.gross_margin = stock_data.get('gross_margin')
            fund.shares_outstanding = stock_data.get('shares_outstanding')
            fund.perf_1m = stock_data.get('perf_1m')
            fund.perf_3m = stock_data.get('perf_3m')
            fund.perf_6m = stock_data.get('perf_6m')
            fund.perf_12m = stock_data.get('perf_12m')
            fund.piotroski_f_score = stock_data.get('piotroski_f_score')
            fund.data_source = 'tradingview'
            fund.fetched_date = today
            
            # Update stock metadata if exists
            if db_ticker in existing_stocks:
                stock = existing_stocks[db_ticker]
                if stock_data.get('market_cap'):
                    stock.market_cap_msek = stock_data['market_cap'] / 1e6
                if stock_data.get('sector'):
                    stock.sector = stock_data['sector']
                # Update ISIN in stocks table
                if stock_data.get('isin'):
                    stock.isin = stock_data['isin']
            
            # Save weekly snapshot for historical backtesting
            if save_snapshot:
                db.add(FundamentalsSnapshot(
                    snapshot_date=today, ticker=db_ticker,
                    market_cap=stock_data.get('market_cap'),
                    pe=stock_data.get('pe'), pb=stock_data.get('pb'), ps=stock_data.get('ps'),
                    p_fcf=stock_data.get('p_fcf'), ev_ebitda=stock_data.get('ev_ebitda'),
                    roe=stock_data.get('roe'), roa=stock_data.get('roa'),
                    roic=stock_data.get('roic'), fcfroe=stock_data.get('fcfroe'),
                    dividend_yield=stock_data.get('dividend_yield'),
                ))
                snapshots_saved += 1
            
            updated += 1
        
        # Flush fundamentals before prices to avoid batch conflicts
        db.flush()
        
        # Save daily prices for portfolio tracking using raw SQL upsert
        from sqlalchemy import text
        prices_saved = 0
        for stock_data in stocks:
            close_price = stock_data.get('close')
            if not close_price:
                continue
            db_ticker = stock_data['db_ticker']
            # SQLite upsert - insert or update on conflict
            db.execute(text("""
                INSERT INTO daily_prices (ticker, date, close) VALUES (:ticker, :date, :close)
                ON CONFLICT(ticker, date) DO UPDATE SET close = :close
            """), {"ticker": db_ticker, "date": today, "close": close_price})
            prices_saved += 1
        db.flush()
        
        # Update ISIN lookup table for CSV import matching
        from models import IsinLookup
        isin_updated = 0
        for stock_data in stocks:
            isin = stock_data.get('isin')
            if not isin:
                continue
            lookup = db.query(IsinLookup).filter(IsinLookup.isin == isin).first()
            if not lookup:
                lookup = IsinLookup(isin=isin)
                db.add(lookup)
            lookup.ticker = stock_data['db_ticker']
            lookup.name = stock_data.get('name')
            lookup.currency = 'SEK'  # Swedish stocks
            lookup.market = 'sweden'
            lookup.updated_at = datetime.now()
            isin_updated += 1
        
        # Also fetch Nordic stocks for ISIN lookup (DK, FI, NO)
        try:
            nordic_stocks = fetcher.fetch_nordic(markets=['denmark', 'finland', 'norway'], min_market_cap_sek=0)
            for stock_data in nordic_stocks:
                isin = stock_data.get('isin')
                if not isin:
                    continue
                
                # Use market-prefixed ticker for Nordic to avoid collisions with Swedish
                market = stock_data.get('market', 'nordic')
                base_ticker = stock_data.get('ticker', stock_data.get('db_ticker'))
                market_suffix = {'finland': '.HE', 'denmark': '.CO', 'norway': '.OL'}.get(market, '')
                prefixed_ticker = f"{base_ticker}{market_suffix}" if market_suffix else base_ticker
                
                lookup = db.query(IsinLookup).filter(IsinLookup.isin == isin).first()
                if not lookup:
                    lookup = IsinLookup(isin=isin)
                    db.add(lookup)
                lookup.ticker = prefixed_ticker
                lookup.name = stock_data.get('name')
                lookup.currency = stock_data.get('currency', 'EUR')
                lookup.market = market
                lookup.updated_at = datetime.now()
                isin_updated += 1
                
                # Save daily price for Nordic stocks with market suffix
                close_price = stock_data.get('close')
                if close_price and prefixed_ticker:
                    db.execute(text("""
                        INSERT INTO daily_prices (ticker, date, close) VALUES (:ticker, :date, :close)
                        ON CONFLICT(ticker, date) DO UPDATE SET close = :close
                    """), {"ticker": prefixed_ticker, "date": today, "close": close_price})
                    prices_saved += 1
        except Exception as e:
            logger.warning(f"Nordic ISIN sync failed: {e}")
        
        db.commit()
        
        # Compute rankings using TradingView data
        from services.ranking_cache import compute_all_rankings_tv, compute_nordic_momentum
        rankings_result = compute_all_rankings_tv(db)
        
        # Save daily rankings snapshot for historical rank tracking
        from models import RankingsSnapshot
        import json
        try:
            nordic_result = compute_nordic_momentum(db)
            if 'rankings' in nordic_result:
                # Store compact format: [{ticker, rank, isin}]
                snapshot_data = [
                    {'ticker': r['ticker'], 'rank': r['rank'], 'isin': r.get('isin')}
                    for r in nordic_result['rankings']
                ]
                snapshot = RankingsSnapshot(
                    strategy='nordic_momentum',
                    snapshot_date=today,
                    rankings_json=json.dumps(snapshot_data)
                )
                db.add(snapshot)
                db.commit()
                logger.info(f"Saved daily rankings snapshot: {len(snapshot_data)} stocks")
        except Exception as e:
            logger.warning(f"Failed to save rankings snapshot: {e}")
        
        elapsed = time.time() - start_time
        
        return {
            "status": "SUCCESS",
            "stocks_updated": updated,
            "isin_updated": isin_updated,
            "snapshots_saved": snapshots_saved,
            "prices_saved": prices_saved,
            "source": "tradingview",
            "duration_seconds": round(elapsed, 2),
            "rankings": rankings_result
        }
        
    except Exception as e:
        logger.error(f"TradingView sync failed: {e}")
        return {"status": "ERROR", "message": str(e)}


def sync_job(is_retry: bool = False):
    """Job to sync all stock data (fundamentals + prices)."""
    global _sync_retry_count
    
    if is_retry:
        logger.info(f"Starting RETRY sync (attempt {_sync_retry_count + 1}/{_MAX_RETRIES})")
    else:
        logger.info(f"Starting scheduled sync (source: {DATA_SOURCE})")
        _sync_retry_count = 0
    
    db = SessionLocal()
    sync_success = False
    
    try:
        # TradingView is the only data source - no fallback
        result = asyncio.run(tradingview_sync(db))
        if result.get('status') == 'ERROR':
            raise Exception(f"TradingView sync failed: {result.get('message', 'Unknown error')}")
        
        logger.info(f"Sync complete: {result}")
        sync_success = True
        _sync_retry_count = 0
        
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
            
        # Sync Nordic momentum rankings
        try:
            from services.ranking_cache import compute_nordic_momentum
            nordic_result = compute_nordic_momentum(db)
            if nordic_result.get('error'):
                logger.error(f"Nordic momentum sync failed: {nordic_result['error']}")
            else:
                logger.info(f"Nordic momentum synced: {len(nordic_result.get('rankings', []))} stocks")
        except Exception as nordic_err:
            logger.error(f"Nordic momentum sync error: {nordic_err}")
        
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
        from services.email_notifications import send_monthly_portfolio_alerts
        from config.settings import get_settings
        from datetime import date
        
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
        
        # Monthly portfolio alerts on 1st of month - send to ALL users with top 40 + rebalance info
        if date.today().day == 1:
            logger.info("Sending monthly rankings emails to all users")
            from services.email_notifications import generate_monthly_rankings_email
            alert_result = generate_monthly_rankings_email(db)
            logger.info(f"Monthly rankings emails: {alert_result}")
        
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


def cleanup_old_data_job():
    """Weekly cleanup of logs only - prices kept for backtesting."""
    logger.info("Starting weekly cleanup")
    db = SessionLocal()
    try:
        from datetime import date, timedelta
        from models import DataSyncLog
        
        # Only clean logs (keep 30 days) - prices needed for backtesting
        log_cutoff = date.today() - timedelta(days=30)
        deleted_logs = db.query(DataSyncLog).filter(DataSyncLog.started_at < log_cutoff).delete()
        db.commit()
        
        logger.info(f"Cleanup complete: {deleted_logs} old logs deleted")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()


def rebalance_reminder_job():
    """Send push notifications for upcoming rebalance dates based on user preferences."""
    logger.info("Checking rebalance reminders")
    db = SessionLocal()
    try:
        from datetime import date
        from models import User, PushSubscription
        from services.push_notifications import send_to_user
        
        today = date.today()
        
        # Get all users with push subscriptions
        users_with_push = db.query(User).join(PushSubscription).distinct().all()
        
        for user in users_with_push:
            freq = user.rebalance_frequency or "quarterly"
            day = user.rebalance_day or 15
            
            # Determine rebalance months
            if freq == "monthly":
                months = list(range(1, 13))
            else:
                months = [3, 6, 9, 12]
            
            # Find next rebalance date for this user
            for month in months:
                year = today.year if month >= today.month else today.year + 1
                rebalance_date = date(year, month, day)
                if rebalance_date > today:
                    days_until = (rebalance_date - today).days
                    
                    if days_until in [3, 1, 0]:
                        if days_until == 3:
                            title, body = "📅 Ombalansering om 3 dagar", f"Dags att förbereda din portfölj ({rebalance_date.strftime('%d %b')})"
                        elif days_until == 1:
                            title, body = "⏰ Ombalansering imorgon!", "Glöm inte att ombalansera din portfölj"
                        else:
                            title, body = "🔔 Dags att ombalansera!", "Idag är det ombalanseringsdag"
                        
                        sent = send_to_user(db, user.id, title, body, "/dashboard")
                        if sent:
                            logger.info(f"Sent reminder to user {user.id} ({days_until} days)")
                    break  # Only check next upcoming date
                
    except Exception as e:
        logger.error(f"Rebalance reminder job failed: {e}")
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
    
    # Weekly cleanup on Sundays at 4 AM UTC
    scheduler.add_job(
        cleanup_old_data_job,
        CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="weekly_cleanup",
        replace_existing=True
    )
    
    # Rebalance reminder check daily at 7 AM UTC
    scheduler.add_job(
        rebalance_reminder_job,
        CronTrigger(hour=7, minute=0),
        id="rebalance_reminder",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info(f"Scheduler started: sync at {settings.data_sync_hour}:00, reports at 08:00, cleanup Sundays 04:00 UTC")

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
