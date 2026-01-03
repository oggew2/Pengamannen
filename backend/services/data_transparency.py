"""
Data transparency and user visibility improvements.
Shows real-time sync progress, data freshness, and missing data alerts.
"""
from datetime import datetime, timedelta
from typing import Dict
import logging
from models import Stock, Fundamentals

logger = logging.getLogger(__name__)


class DataTransparencyService:
    """Service to provide complete data transparency to users."""
    
    @staticmethod
    def get_detailed_data_status(db) -> Dict:
        """Get data status using strategy-eligible stocks as baseline.
        
        Uses is_active=1 stocks (those with fundamentals) as the meaningful baseline,
        not all 7,000+ stocks in the database.
        """
        try:
            now = datetime.now()
            
            # Strategy-eligible = stocks with is_active=1 (have fundamentals)
            # This is the meaningful baseline for data quality
            active_stocks = db.query(Stock).filter(
                Stock.stock_type.in_(['stock', 'sdb']),
                Stock.is_active == True
            ).all()
            
            total_stocks = len(active_stocks)
            if total_stocks == 0:
                return {
                    'system_status': 'NO_DATA',
                    'system_message': 'No active stocks found. Run sync first.',
                    'can_run_strategies': False,
                    'summary': {'total_stocks': 0, 'fresh_count': 0, 'fresh_percentage': 0}
                }
            
            # Check freshness of fundamentals for active stocks
            fresh_count = 0
            stale_count = 0
            very_stale_count = 0
            
            for stock in active_stocks:
                fund = db.query(Fundamentals).filter(
                    Fundamentals.ticker == stock.ticker
                ).first()
                
                if fund and fund.fetched_date:
                    age_days = (now.date() - fund.fetched_date).days
                    if age_days <= 1:
                        fresh_count += 1
                    elif age_days <= 3:
                        stale_count += 1
                    else:
                        very_stale_count += 1
            
            fresh_percentage = (fresh_count / total_stocks * 100) if total_stocks > 0 else 0
            
            # Determine status
            if fresh_percentage >= 90:
                system_status = 'EXCELLENT'
                system_message = f'Data current: {fresh_count}/{total_stocks} stocks fresh'
                can_run = True
            elif fresh_percentage >= 70:
                system_status = 'GOOD'
                system_message = f'Most data current: {fresh_count}/{total_stocks} fresh'
                can_run = True
            elif fresh_percentage >= 50:
                system_status = 'DEGRADED'
                system_message = f'Some stale data: {fresh_count}/{total_stocks} fresh'
                can_run = True
            else:
                system_status = 'STALE'
                system_message = f'Data needs refresh: {fresh_count}/{total_stocks} fresh'
                can_run = True  # Still allow strategies, just warn
            
            return {
                'system_status': system_status,
                'system_message': system_message,
                'can_run_strategies': can_run,
                'last_checked': now.isoformat(),
                'summary': {
                    'total_stocks': total_stocks,
                    'fresh_count': fresh_count,
                    'stale_count': stale_count,
                    'very_stale_count': very_stale_count,
                    'fresh_percentage': round(fresh_percentage, 1)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting data status: {e}")
            return {
                'system_status': 'ERROR',
                'system_message': f'Cannot check data status: {str(e)}',
                'can_run_strategies': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_sync_progress() -> Dict:
        """Get sync time estimates."""
        return {
            'estimated_sync_time_seconds': 60,
            'rate_limit_info': 'Avanza API: ~100 requests/second',
            'last_sync_duration': None
        }


def validate_strategy_data_quality(db, strategy_name: str) -> Dict:
    """Check if strategy can run with current data quality."""
    service = DataTransparencyService()
    status = service.get_detailed_data_status(db)
    
    return {
        'strategy': strategy_name,
        'can_run': status.get('can_run_strategies', False),
        'data_status': status.get('system_status'),
        'message': status.get('system_message'),
        'fresh_percentage': status.get('summary', {}).get('fresh_percentage', 0)
    }
