"""
Data integrity checks for trading-critical data validation.
Ensures data is complete and accurate before strategy calculations.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

# Thresholds for alerts
CRITICAL_THRESHOLDS = {
    "max_data_age_hours": 48,           # Data older than 48h = CRITICAL
    "warning_data_age_hours": 24,       # Data older than 24h = WARNING
    "min_stocks_for_strategy": 50,      # Need at least 50 stocks with data
    "min_fundamentals_coverage_pct": 80, # 80% of stocks must have fundamentals
    "min_price_coverage_pct": 90,       # 90% of stocks must have recent prices
    "max_failed_stocks_pct": 10,        # Max 10% failed syncs allowed
}


class DataIntegrityChecker:
    """Validates data integrity before strategy calculations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []
        
    def run_all_checks(self) -> Dict:
        """Run all integrity checks and return comprehensive report."""
        import os
        self.issues = []
        self.warnings = []
        
        # Check data source - TradingView uses live prices, not DailyPrice table
        data_source = os.getenv('DATA_SOURCE', 'tradingview')
        
        checks = {
            "data_freshness": self._check_data_freshness(),
            "fundamentals_coverage": self._check_fundamentals_coverage(),
            "missing_critical_fields": self._check_critical_fields(),
            "market_cap_filter": self._check_market_cap_data(),
            "active_stock_count": self._check_active_stock_count(),
        }
        
        # Only check price coverage and sync failures for Avanza source
        if data_source != 'tradingview':
            checks["price_coverage"] = self._check_price_coverage()
            checks["sync_failures"] = self._check_sync_failures()
        
        # Determine overall status
        has_critical = any(c.get("status") == "CRITICAL" for c in checks.values())
        has_warning = any(c.get("status") == "WARNING" for c in checks.values())
        
        if has_critical:
            overall_status = "CRITICAL"
            recommendation = "DO NOT USE FOR TRADING - Data integrity issues detected"
        elif has_warning:
            overall_status = "WARNING"
            recommendation = "Review warnings before trading - Some data may be stale or incomplete"
        else:
            overall_status = "OK"
            recommendation = "Data integrity verified - Safe to use for trading"
        
        return {
            "status": overall_status,
            "recommendation": recommendation,
            "checked_at": datetime.now().isoformat(),
            "checks": checks,
            "issues": self.issues,
            "warnings": self.warnings,
            "safe_to_trade": overall_status == "OK"
        }
    
    def _check_data_freshness(self) -> Dict:
        """Check if data is fresh enough for trading."""
        from models import Fundamentals, DailyPrice
        
        now = datetime.now()
        
        # Check fundamentals freshness
        latest_fund = self.db.query(func.max(Fundamentals.fetched_date)).scalar()
        # Check price freshness
        latest_price = self.db.query(func.max(DailyPrice.date)).scalar()
        
        fund_age_hours = None
        price_age_hours = None
        
        if latest_fund:
            fund_age = now.date() - latest_fund
            fund_age_hours = fund_age.days * 24
        
        if latest_price:
            price_age = now.date() - latest_price
            price_age_hours = price_age.days * 24
        
        # Determine status
        status = "OK"
        message = "Data is fresh"
        
        if fund_age_hours is None or price_age_hours is None:
            status = "CRITICAL"
            message = "No data found"
            self.issues.append({"type": "NO_DATA", "message": message})
        elif fund_age_hours > CRITICAL_THRESHOLDS["max_data_age_hours"]:
            status = "CRITICAL"
            message = f"Fundamentals are {fund_age_hours}h old (max: {CRITICAL_THRESHOLDS['max_data_age_hours']}h)"
            self.issues.append({"type": "STALE_FUNDAMENTALS", "message": message, "age_hours": fund_age_hours})
        elif fund_age_hours > CRITICAL_THRESHOLDS["warning_data_age_hours"]:
            status = "WARNING"
            message = f"Fundamentals are {fund_age_hours}h old"
            self.warnings.append({"type": "AGING_FUNDAMENTALS", "message": message, "age_hours": fund_age_hours})
        
        return {
            "status": status,
            "message": message,
            "latest_fundamentals": latest_fund.isoformat() if latest_fund else None,
            "latest_price": latest_price.isoformat() if latest_price else None,
            "fundamentals_age_hours": fund_age_hours,
            "price_age_hours": price_age_hours
        }
    
    def _check_fundamentals_coverage(self) -> Dict:
        """Check what percentage of active stocks have fundamentals."""
        from models import Stock, Fundamentals
        
        # Count active stocks only (stocks we expect to have data for)
        active_stocks = self.db.query(Stock).filter(
            Stock.stock_type.in_(['stock', 'sdb']),
            Stock.is_active == True
        ).count()
        
        stocks_with_fund = self.db.query(Fundamentals.ticker).distinct().count()
        
        if active_stocks == 0:
            # No active stocks marked - use fundamentals count as baseline
            return {
                "status": "OK",
                "message": f"{stocks_with_fund} stocks with fundamentals",
                "total_active_stocks": stocks_with_fund,
                "stocks_with_fundamentals": stocks_with_fund,
                "coverage_pct": 100.0,
                "missing_count": 0
            }
        
        coverage_pct = (stocks_with_fund / active_stocks) * 100 if active_stocks > 0 else 0
        
        # Find active stocks missing fundamentals
        stocks_with_fund_set = set(r[0] for r in self.db.query(Fundamentals.ticker).distinct().all())
        active_tickers = set(r[0] for r in self.db.query(Stock.ticker).filter(
            Stock.stock_type.in_(['stock', 'sdb']),
            Stock.is_active == True
        ).all())
        missing = active_tickers - stocks_with_fund_set
        
        status = "OK"
        message = f"{coverage_pct:.1f}% coverage ({stocks_with_fund}/{active_stocks} active stocks)"
        
        if coverage_pct < CRITICAL_THRESHOLDS["min_fundamentals_coverage_pct"]:
            status = "CRITICAL" if coverage_pct < 50 else "WARNING"
            message = f"Only {coverage_pct:.1f}% of active stocks have fundamentals"
            self.issues.append({
                "type": "LOW_FUNDAMENTALS_COVERAGE",
                "message": message,
                "missing_count": len(missing),
                "missing_tickers": list(missing)[:20]
            })
        
        return {
            "status": status,
            "message": message,
            "total_active_stocks": active_stocks,
            "stocks_with_fundamentals": stocks_with_fund,
            "coverage_pct": round(coverage_pct, 1),
            "missing_count": len(missing),
            "missing_sample": list(missing)[:10]
        }
    
    def _check_price_coverage(self) -> Dict:
        """Check what percentage of active stocks have recent prices."""
        from models import Stock, DailyPrice, Fundamentals
        
        # Count active stocks only
        active_stocks = self.db.query(Stock).filter(
            Stock.stock_type.in_(['stock', 'sdb']),
            Stock.is_active == True
        ).count()
        
        if active_stocks == 0:
            active_stocks = self.db.query(Fundamentals.ticker).distinct().count()
        
        recent_date = date.today() - timedelta(days=7)
        
        stocks_with_prices = self.db.query(DailyPrice.ticker).filter(
            DailyPrice.date >= recent_date
        ).distinct().count()
        
        if active_stocks == 0:
            return {"status": "CRITICAL", "message": "No active stocks", "coverage_pct": 0}
        
        coverage_pct = (stocks_with_prices / active_stocks) * 100
        
        status = "OK"
        message = f"{coverage_pct:.1f}% have recent prices"
        
        if coverage_pct < CRITICAL_THRESHOLDS["min_price_coverage_pct"]:
            status = "WARNING"
            message = f"Only {coverage_pct:.1f}% of active stocks have prices from last 7 days"
            self.warnings.append({"type": "LOW_PRICE_COVERAGE", "message": message})
        
        return {
            "status": status,
            "message": message,
            "total_active_stocks": active_stocks,
            "stocks_with_recent_prices": stocks_with_prices,
            "coverage_pct": round(coverage_pct, 1)
        }
    
    def _check_sync_failures(self) -> Dict:
        """Check for recent sync failures."""
        from models import SyncLog
        
        try:
            recent = self.db.query(SyncLog).order_by(SyncLog.timestamp.desc()).limit(10).all()
            if not recent:
                return {"status": "OK", "message": "No sync history", "recent_syncs": []}
            
            failures = [s for s in recent if not s.success]
            last_sync = recent[0]
            
            status = "OK"
            message = f"Last sync: {last_sync.timestamp}"
            
            if failures:
                fail_pct = (len(failures) / len(recent)) * 100
                if fail_pct > 50:
                    status = "CRITICAL"
                    message = f"{len(failures)}/{len(recent)} recent syncs failed"
                    self.issues.append({
                        "type": "SYNC_FAILURES",
                        "message": message,
                        "errors": [f.error_message for f in failures if f.error_message]
                    })
                elif fail_pct > 20:
                    status = "WARNING"
                    message = f"{len(failures)}/{len(recent)} recent syncs had issues"
                    self.warnings.append({"type": "SYNC_ISSUES", "message": message})
            
            return {
                "status": status,
                "message": message,
                "last_sync": last_sync.timestamp.isoformat() if last_sync else None,
                "last_sync_success": last_sync.success if last_sync else None,
                "recent_failures": len(failures),
                "recent_total": len(recent)
            }
        except Exception as e:
            return {"status": "OK", "message": "Sync logging not configured", "error": str(e)}
    
    def _check_critical_fields(self) -> Dict:
        """Check that critical fields for strategies are populated."""
        from models import Fundamentals
        
        # Fields needed for each strategy
        momentum_fields = ['market_cap']  # For filtering, F-score uses multiple
        value_fields = ['pe', 'pb', 'ps', 'ev_ebitda', 'dividend_yield', 'market_cap']
        quality_fields = ['roe', 'roa', 'roic', 'fcfroe', 'market_cap']
        
        all_critical = set(momentum_fields + value_fields + quality_fields)
        
        total = self.db.query(Fundamentals).count()
        if total == 0:
            return {"status": "CRITICAL", "message": "No fundamentals data"}
        
        field_coverage = {}
        missing_fields = []
        
        for field in all_critical:
            if hasattr(Fundamentals, field):
                non_null = self.db.query(Fundamentals).filter(
                    getattr(Fundamentals, field) != None
                ).count()
                coverage = (non_null / total) * 100
                field_coverage[field] = round(coverage, 1)
                
                if coverage < 50:
                    missing_fields.append({"field": field, "coverage_pct": coverage})
        
        status = "OK"
        message = "Critical fields populated"
        
        if missing_fields:
            status = "WARNING"
            message = f"{len(missing_fields)} fields have low coverage"
            self.warnings.append({
                "type": "LOW_FIELD_COVERAGE",
                "message": message,
                "fields": missing_fields
            })
        
        return {
            "status": status,
            "message": message,
            "field_coverage": field_coverage,
            "low_coverage_fields": missing_fields
        }
    
    def _check_market_cap_data(self) -> Dict:
        """Check market cap data for universe filtering."""
        from models import Fundamentals
        
        # Count stocks above 2B SEK threshold
        min_cap = 2_000_000_000  # 2B SEK
        
        total = self.db.query(Fundamentals).count()
        with_mcap = self.db.query(Fundamentals).filter(Fundamentals.market_cap != None).count()
        above_threshold = self.db.query(Fundamentals).filter(Fundamentals.market_cap >= min_cap).count()
        
        if total == 0:
            return {"status": "CRITICAL", "message": "No data"}
        
        mcap_coverage = (with_mcap / total) * 100
        
        status = "OK"
        message = f"{above_threshold} stocks above 2B SEK threshold"
        
        if mcap_coverage < 80:
            status = "WARNING"
            message = f"Only {mcap_coverage:.1f}% have market cap data"
            self.warnings.append({"type": "LOW_MCAP_COVERAGE", "message": message})
        
        if above_threshold < CRITICAL_THRESHOLDS["min_stocks_for_strategy"]:
            status = "CRITICAL"
            message = f"Only {above_threshold} stocks above threshold (need {CRITICAL_THRESHOLDS['min_stocks_for_strategy']})"
            self.issues.append({"type": "INSUFFICIENT_UNIVERSE", "message": message})
        
        return {
            "status": status,
            "message": message,
            "total_stocks": total,
            "with_market_cap": with_mcap,
            "above_2b_threshold": above_threshold,
            "market_cap_coverage_pct": round(mcap_coverage, 1)
        }
    
    def _check_active_stock_count(self) -> Dict:
        """Check that we have a reasonable number of active stocks."""
        from models import Stock
        
        MIN_EXPECTED_ACTIVE = 500  # Swedish market should have 600-800 stocks
        
        active_count = self.db.query(Stock).filter(
            Stock.stock_type.in_(['stock', 'sdb']),
            Stock.is_active == True
        ).count()
        
        status = "OK"
        message = f"{active_count} active stocks"
        
        if active_count < MIN_EXPECTED_ACTIVE:
            status = "CRITICAL"
            message = f"Only {active_count} active stocks (expected >{MIN_EXPECTED_ACTIVE}). Possible sync failure."
            self.issues.append({
                "type": "LOW_ACTIVE_STOCKS",
                "message": message,
                "count": active_count,
                "min_expected": MIN_EXPECTED_ACTIVE
            })
        
        return {
            "status": status,
            "message": message,
            "active_count": active_count,
            "min_expected": MIN_EXPECTED_ACTIVE
        }


def check_data_integrity(db: Session) -> Dict:
    """Main entry point for data integrity checks."""
    checker = DataIntegrityChecker(db)
    return checker.run_all_checks()


def get_failed_stocks_from_last_sync(db: Session) -> List[Dict]:
    """Get list of stocks that failed in the last sync."""
    from models import SyncLog
    import json
    
    try:
        last_sync = db.query(SyncLog).order_by(SyncLog.timestamp.desc()).first()
        if last_sync and last_sync.details_json:
            details = json.loads(last_sync.details_json)
            return details.get("failed_stocks", [])
    except:
        pass
    return []


def validate_before_strategy(db: Session, strategy_name: str) -> Tuple[bool, str, List[Dict]]:
    """
    Validate data integrity before running a strategy.
    Returns: (is_safe, message, issues)
    """
    checker = DataIntegrityChecker(db)
    result = checker.run_all_checks()
    
    if result["status"] == "CRITICAL":
        return False, result["recommendation"], result["issues"]
    
    return True, "Data validated", result["warnings"]
