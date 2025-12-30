"""
Data transparency and user visibility improvements.
Shows real-time sync progress, data freshness, and missing data alerts.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from models import Stock, Fundamentals, DailyPrice

logger = logging.getLogger(__name__)

class DataTransparencyService:
    """Service to provide complete data transparency to users."""
    
    @staticmethod
    def get_detailed_data_status(db) -> Dict:
        """Get comprehensive data status with per-stock details."""
        try:
            now = datetime.now()
            
            # Get all stocks and their last update times
            stocks_query = db.query(Stock).all()
            fundamentals_query = db.query(Fundamentals).all()
            
            # Create stock status map
            stock_status = {}
            for stock in stocks_query:
                stock_status[stock.ticker] = {
                    'name': stock.name,
                    'sector': stock.sector,
                    'market_cap': stock.market_cap_msek,
                    'last_fundamental_update': None,
                    'last_price_update': None,
                    'data_age_hours': None,
                    'status': 'NO_DATA'
                }
            
            # Add fundamental data timestamps
            for fund in fundamentals_query:
                if fund.ticker in stock_status:
                    stock_status[fund.ticker]['last_fundamental_update'] = fund.fetched_date
                    if fund.fetched_date:
                        age = (now.date() - fund.fetched_date).days * 24
                        stock_status[fund.ticker]['data_age_hours'] = age
                        
                        # Classify data freshness
                        if age <= 24:
                            stock_status[fund.ticker]['status'] = 'FRESH'
                        elif age <= 72:
                            stock_status[fund.ticker]['status'] = 'STALE'
                        else:
                            stock_status[fund.ticker]['status'] = 'VERY_STALE'
            
            # Calculate summary statistics
            total_stocks = len(stock_status)
            fresh_count = sum(1 for s in stock_status.values() if s['status'] == 'FRESH')
            stale_count = sum(1 for s in stock_status.values() if s['status'] == 'STALE')
            very_stale_count = sum(1 for s in stock_status.values() if s['status'] == 'VERY_STALE')
            no_data_count = sum(1 for s in stock_status.values() if s['status'] == 'NO_DATA')
            
            # Determine overall system status
            fresh_percentage = (fresh_count / total_stocks * 100) if total_stocks > 0 else 0
            
            if fresh_percentage >= 90:
                system_status = 'EXCELLENT'
                system_message = f'Data is current: {fresh_count}/{total_stocks} stocks fresh'
                can_run_strategies = True
            elif fresh_percentage >= 70:
                system_status = 'GOOD'
                system_message = f'Most data current: {fresh_count}/{total_stocks} stocks fresh, {stale_count} stale'
                can_run_strategies = True
            elif fresh_percentage >= 50:
                system_status = 'DEGRADED'
                system_message = f'Data quality degraded: {fresh_count}/{total_stocks} fresh, {stale_count + very_stale_count} stale'
                can_run_strategies = True
            else:
                system_status = 'CRITICAL'
                system_message = f'Data too stale: Only {fresh_count}/{total_stocks} stocks current'
                can_run_strategies = False
            
            # Find most stale stocks
            stale_stocks = [
                {'ticker': ticker, 'name': data['name'], 'age_hours': data['data_age_hours']}
                for ticker, data in stock_status.items()
                if data['status'] in ['STALE', 'VERY_STALE', 'NO_DATA']
            ]
            stale_stocks.sort(key=lambda x: x['age_hours'] or 999999, reverse=True)
            
            return {
                'system_status': system_status,
                'system_message': system_message,
                'can_run_strategies': can_run_strategies,
                'last_checked': now.isoformat(),
                'summary': {
                    'total_stocks': total_stocks,
                    'fresh_count': fresh_count,
                    'stale_count': stale_count,
                    'very_stale_count': very_stale_count,
                    'no_data_count': no_data_count,
                    'fresh_percentage': round(fresh_percentage, 1)
                },
                'most_stale_stocks': stale_stocks[:10],  # Top 10 most stale
                'stock_details': stock_status,
                'data_age_legend': {
                    'FRESH': '< 24 hours',
                    'STALE': '24-72 hours', 
                    'VERY_STALE': '> 72 hours',
                    'NO_DATA': 'Never updated'
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
        """Get real-time sync progress (would need Redis/cache for production)."""
        # This would typically use Redis or similar for real-time progress
        # For now, return static info about expected times
        
        sync_estimates = {
            'sweden_large': {
                'stocks': 30,
                'estimated_minutes': '8-15 minutes',
                'per_stock_seconds': '15-30 seconds'
            },
            'sweden_all': {
                'stocks': 400,
                'estimated_minutes': '100-200 minutes (1.7-3.3 hours)',
                'per_stock_seconds': '15-30 seconds'
            },
            'nordic_large': {
                'stocks': 120,
                'estimated_minutes': '30-60 minutes',
                'per_stock_seconds': '15-30 seconds'
            },
            'nordic_all': {
                'stocks': 880,
                'estimated_minutes': '220-440 minutes (3.7-7.3 hours)',
                'per_stock_seconds': '15-30 seconds'
            }
        }
        
        return {
            'rate_limiting_info': {
                'base_delay': '15-30 seconds between requests',
                'exponential_backoff': 'Up to 10 minutes on failures',
                'circuit_breaker': '30 minutes timeout after 5 failures',
                'user_agent_rotation': 'Automatic on 429 errors'
            },
            'sync_estimates': sync_estimates,
            'recommendations': {
                'sweden_large': 'Recommended for daily updates',
                'sweden_all': 'Use for weekly full refresh',
                'nordic_large': 'Good for Nordic coverage',
                'nordic_all': 'Monthly full refresh only'
            }
        }
    
    @staticmethod
    def get_strategy_data_requirements() -> Dict:
        """Show which strategies can run with current data quality."""
        return {
            'sammansatt_momentum': {
                'min_stocks_required': 20,
                'data_freshness_required': '< 48 hours',
                'critical_fields': ['pe', 'pb', 'roe', 'roa', 'market_cap']
            },
            'trendande_varde': {
                'min_stocks_required': 25,
                'data_freshness_required': '< 72 hours',
                'critical_fields': ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda', 'dividend_yield']
            },
            'trendande_utdelning': {
                'min_stocks_required': 20,
                'data_freshness_required': '< 72 hours',
                'critical_fields': ['dividend_yield', 'payout_ratio']
            },
            'trendande_kvalitet': {
                'min_stocks_required': 25,
                'data_freshness_required': '< 48 hours',
                'critical_fields': ['roe', 'roa', 'roic', 'fcfroe']
            }
        }

def validate_strategy_data_quality(db, strategy_name: str) -> Dict:
    """Validate if specific strategy can run with current data."""
    try:
        transparency = DataTransparencyService()
        data_status = transparency.get_detailed_data_status(db)
        requirements = transparency.get_strategy_data_requirements()
        
        if strategy_name not in requirements:
            return {'can_run': False, 'error': 'Unknown strategy'}
        
        req = requirements[strategy_name]
        
        # Check minimum stock count
        fresh_count = data_status['summary']['fresh_count']
        stale_count = data_status['summary']['stale_count']
        usable_count = fresh_count + stale_count  # Allow stale data for some strategies
        
        if usable_count < req['min_stocks_required']:
            return {
                'can_run': False,
                'reason': f'Insufficient data: {usable_count}/{req["min_stocks_required"]} stocks available',
                'missing_count': req['min_stocks_required'] - usable_count
            }
        
        # Check data freshness
        if '48 hours' in req['data_freshness_required'] and fresh_count < req['min_stocks_required']:
            return {
                'can_run': False,
                'reason': f'Data too stale: {fresh_count} fresh stocks, need {req["min_stocks_required"]}',
                'stale_count': data_status['summary']['stale_count'] + data_status['summary']['very_stale_count']
            }
        
        return {
            'can_run': True,
            'data_quality': 'sufficient',
            'stocks_available': usable_count,
            'fresh_stocks': fresh_count,
            'last_update': data_status['last_checked']
        }
        
    except Exception as e:
        return {'can_run': False, 'error': str(e)}
