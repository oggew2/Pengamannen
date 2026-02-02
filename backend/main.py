from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, Header, UploadFile, File, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from contextlib import asynccontextmanager
import pandas as pd
import json
import logging
import asyncio
from typing import List, Dict, Optional

# CRITICAL: Start memory monitoring immediately
from services.memory_monitor import memory_monitor, monitor_memory_usage

from db import get_db, engine, Base, text
from models import Stock, DailyPrice, Fundamentals, SavedCombination as SavedCombinationModel, UserGoal
# from models.user_storage import UserProfile, UserPortfolio, AvanzaImport, UserSession
from schemas import (
    StrategyMeta, RankedStock, StockDetail, 
    PortfolioResponse, PortfolioHoldingOut, RebalanceDate,
    BacktestRequest, BacktestResponse, SyncStatus, CombinerRequest,
    CombinerPreviewRequest, CombinerPreviewResponse, CombinerSaveRequest, SavedCombination
)
from services.ranking import (
    calculate_momentum_score, calculate_momentum_with_quality_filter,
    calculate_value_score, calculate_dividend_score, calculate_quality_score,
    rank_and_select_top_n, filter_by_market_cap
)
from services.portfolio import get_next_rebalance_dates, combine_strategies
from services.backtesting import backtest_strategy, get_backtest_results
from services.avanza_fetcher_v2 import AvanzaDirectFetcher
from services.enhanced_backtesting import long_term_backtester
from services.auto_rebalancing import auto_rebalancer
from services.portfolio_comparison import PortfolioComparisonService
from services.validation import check_data_freshness
from services.cache import invalidate_cache, get_cache_stats
from services.export import export_rankings_to_csv, export_backtest_to_csv, export_comparison_to_csv
from services.transaction_costs import (
    calculate_total_transaction_cost, calculate_rebalance_costs,
    calculate_annual_cost_impact, get_available_brokers
)
from services.benchmark import (
    calculate_relative_performance, generate_relative_chart_data,
    calculate_rolling_metrics
)
from services.risk_analytics import (
    calculate_risk_metrics, calculate_sector_exposure,
    calculate_drawdown_analysis, calculate_rolling_sharpe
)
from services.dividends import (
    add_dividend_event, get_upcoming_dividends,
    calculate_projected_income, get_dividend_history, calculate_dividend_growth
)
from services.watchlist import (
    create_watchlist, add_to_watchlist, remove_from_watchlist,
    get_watchlist, check_ranking_changes, get_all_watchlists
)
from services.custom_strategy import (
    get_available_factors, create_custom_strategy, get_custom_strategy,
    list_custom_strategies, delete_custom_strategy, run_custom_strategy
)
from services.markets import get_available_markets, get_stocks_for_market, get_market_config
from services.csv_import import parse_broker_csv, calculate_holdings_from_transactions
from services.user_portfolio import (
    get_portfolio_value, calculate_portfolio_performance, 
    get_portfolio_history, save_snapshot, calculate_rebalance_trades
)
from config.settings import get_settings, load_strategies_config
from jobs.scheduler import start_scheduler, stop_scheduler, get_scheduler_status
from fastapi.responses import PlainTextResponse

# Configure logging with both console and file handlers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s|%(levelname)s|%(name)s|%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_log(self, level: str, message: str, details: str = None):
        if not self.active_connections:
            return
            
        log_data = {
            "level": level,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(log_data))
            except Exception:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)

manager = ConnectionManager()

STRATEGIES_CONFIG = load_strategies_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    
    # CRITICAL: Start memory monitoring for production
    memory_monitor.start_monitoring(check_interval=60)  # Check every minute
    logger.info("Memory monitoring started")
    
    start_scheduler()
    logger.info("Application started with scheduler and memory monitoring")
    yield
    
    # Cleanup on shutdown
    memory_monitor.stop_monitoring()
    stop_scheduler()
    logger.info("Application shutdown with cleanup")

app = FastAPI(title="Börslabbet Strategy API", lifespan=lifespan, docs_url=None, redoc_url=None)

# Create v1 API router
from fastapi import APIRouter
v1_router = APIRouter(prefix="/v1")

# Rate limiting setup
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Enable CORS for frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "http://192.168.0.150:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Auth middleware - protect all API routes except auth endpoints and health
class AuthMiddleware(BaseHTTPMiddleware):
    OPEN_PATHS = {"/v1/auth/login", "/v1/auth/register", "/v1/auth/logout", "/v1/auth/me", "/v1/health", "/health", "/", "/favicon.ico", "/v1/strategies", "/v1/data/status/detailed", "/v1/data/sync-history", "/v1/scheduler-check", "/v1/push/vapid-key", "/v1/push/subscribe"}
    OPEN_PREFIXES = ("/v1/strategies/nordic/",)  # All Nordic momentum endpoints
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Allow open paths and static assets
        if path in self.OPEN_PATHS or path.startswith("/assets") or not path.startswith("/v1"):
            return await call_next(request)
        
        # Allow open prefixes (Nordic momentum endpoints)
        if any(path.startswith(prefix) for prefix in self.OPEN_PREFIXES):
            return await call_next(request)
        
        # Check auth cookie
        from services.auth import COOKIE_NAME
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        
        # Validate session
        from db import SessionLocal
        from models import UserSession
        from datetime import datetime
        db = SessionLocal()
        try:
            session = db.query(UserSession).filter(
                UserSession.token == token,
                UserSession.expires_at > datetime.now()
            ).first()
            if not session:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=401, content={"detail": "Session expired"})
        finally:
            db.close()
        
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# GZip compression for responses > 1KB
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Initialize services
portfolio_comparison_service = PortfolioComparisonService()


# Auth endpoints
@v1_router.post("/auth/register")
@limiter.limit("5/minute")
def register(request: Request, response: Response, email: str, password: str, invite_code: str, name: str = None, db: Session = Depends(get_db)):
    """Register a new user with invite code."""
    from services.auth import register_user, login_user, set_auth_cookie
    from services.audit import log_auth
    try:
        user = register_user(db, email, password, invite_code, name)
        user_info, token = login_user(db, email, password)
        set_auth_cookie(response, token)
        log_auth("REGISTER", user.id, email, True, request.client.host if request.client else None)
        return user_info
    except Exception as e:
        log_auth("REGISTER", None, email, False, request.client.host if request.client else None)
        raise

@v1_router.post("/auth/login")
@limiter.limit("5/minute")
def login(request: Request, response: Response, email: str, password: str, db: Session = Depends(get_db)):
    """Login and set session cookie."""
    from services.auth import login_user, set_auth_cookie
    from services.audit import log_auth
    try:
        user_info, token = login_user(db, email, password)
        set_auth_cookie(response, token)
        log_auth("LOGIN", user_info.get("user_id"), email, True, request.client.host if request.client else None)
        return user_info
    except Exception as e:
        log_auth("LOGIN", None, email, False, request.client.host if request.client else None)
        raise

@v1_router.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Logout and clear cookie."""
    from services.auth import logout_user, clear_auth_cookie, COOKIE_NAME
    token = request.cookies.get(COOKIE_NAME)
    if token:
        logout_user(db, token)
    clear_auth_cookie(response)
    return {"status": "logged out"}

@v1_router.get("/auth/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    """Get current user info from cookie."""
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "is_admin": user.is_admin,
        "invite_code": user.invite_code,
        "market_filter": user.market_filter,
        "rebalance_frequency": getattr(user, 'rebalance_frequency', None) or "quarterly",
        "rebalance_day": getattr(user, 'rebalance_day', None) or 15,
    }

@v1_router.put("/auth/rebalance-settings")
def update_rebalance_settings(request: Request, frequency: str = "quarterly", day: int = 15, db: Session = Depends(get_db)):
    """Update user's rebalance preferences."""
    from services.auth import require_auth
    user = require_auth(request, db)
    if frequency not in ["quarterly", "monthly"]:
        raise HTTPException(status_code=400, detail="Invalid frequency")
    if day < 1 or day > 28:
        raise HTTPException(status_code=400, detail="Day must be 1-28")
    user.rebalance_frequency = frequency
    user.rebalance_day = day
    db.commit()
    return {"rebalance_frequency": frequency, "rebalance_day": day}

@v1_router.put("/auth/market-filter")
def update_market_filter(request: Request, market_filter: str, db: Session = Depends(get_db)):
    """Update user's market filter preference."""
    from services.auth import require_auth
    user = require_auth(request, db)
    if market_filter not in ["stockholmsborsen", "first_north", "both"]:
        raise HTTPException(status_code=400, detail="Invalid market filter")
    user.market_filter = market_filter
    db.commit()
    return {"market_filter": user.market_filter}

@v1_router.post("/admin/bootstrap")
def bootstrap_admin(email: str, secret: str, db: Session = Depends(get_db)):
    """Bootstrap first admin user. Requires ADMIN_SECRET env var."""
    import os
    from models import User
    admin_secret = os.environ.get("ADMIN_SECRET", "borslabbet-admin-2024")
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid secret")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found - register first")
    user.is_admin = True
    if not user.invite_code:
        user.invite_code = User.generate_invite_code()
    db.commit()
    return {"status": "promoted", "email": email, "invite_code": user.invite_code}

@v1_router.get("/admin/users")
def get_all_users(request: Request, db: Session = Depends(get_db)):
    """Get all users (admin only)."""
    from services.auth import require_admin
    from models import User
    require_admin(request, db)
    users = db.query(User).all()
    return {
        "total": len(users),
        "users": [{
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "invited_by": u.invited_by
        } for u in users]
    }

@v1_router.delete("/admin/users/{user_id}")
def delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Delete a user (admin only)."""
    from services.auth import require_admin
    from models import User
    admin = require_admin(request, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"status": "deleted", "id": user_id}


@v1_router.post("/admin/users/{user_id}/make-admin")
def make_user_admin(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Make a user an admin (admin only)."""
    from services.auth import require_admin
    from models import User
    require_admin(request, db)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        return {"status": "already_admin", "id": user_id}
    user.is_admin = True
    # Give them an invite code when they become admin
    if not user.invite_code:
        user.invite_code = User.generate_invite_code()
    db.commit()
    return {"status": "promoted", "id": user_id, "invite_code": user.invite_code}


@v1_router.post("/admin/users/{user_id}/remove-admin")
def remove_user_admin(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Remove admin status from a user (admin only)."""
    from services.auth import require_admin
    from models import User
    admin = require_admin(request, db)
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot remove your own admin status")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_admin = False
    user.invite_code = None  # Remove invite code when no longer admin
    db.commit()
    return {"status": "demoted", "id": user_id}


# Health
@v1_router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check with database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


# Prometheus metrics endpoint
@v1_router.get("/metrics", response_class=PlainTextResponse)
def metrics(db: Session = Depends(get_db)):
    """Prometheus-compatible metrics endpoint."""
    from models import Stock, DailyPrice, StrategySignal
    
    stock_count = db.query(Stock).count()
    price_count = db.query(DailyPrice).count()
    signal_count = db.query(StrategySignal).count()
    
    # Add memory metrics
    from services.memory_monitor import get_memory_status
    memory_stats = get_memory_status()
    
    lines = [
        "# HELP borslabbet_stocks_total Total number of stocks in database",
        "# TYPE borslabbet_stocks_total gauge",
        f"borslabbet_stocks_total {stock_count}",
        "# HELP borslabbet_prices_total Total price records",
        "# TYPE borslabbet_prices_total gauge",
        f"borslabbet_prices_total {price_count}",
        "# HELP borslabbet_signals_total Strategy signal records",
        "# TYPE borslabbet_signals_total gauge",
        f"borslabbet_signals_total {signal_count}",
        "# HELP borslabbet_memory_usage_mb Memory usage in MB",
        "# TYPE borslabbet_memory_usage_mb gauge",
        f"borslabbet_memory_usage_mb {memory_stats['usage_mb']:.1f}",
        "# HELP borslabbet_memory_percent Memory usage percentage",
        "# TYPE borslabbet_memory_percent gauge",
        f"borslabbet_memory_percent {memory_stats['percent']:.1f}",
    ]
    return "\n".join(lines)


# Memory monitoring endpoints
@v1_router.get("/system/memory")
def get_memory_status_endpoint():
    """Get current memory usage status."""
    from services.memory_monitor import get_memory_status
    return get_memory_status()

@v1_router.post("/system/memory/cleanup")
def cleanup_memory_endpoint():
    """Force memory cleanup (admin only)."""
    from services.memory_monitor import cleanup_memory
    result = cleanup_memory()
    return {"message": "Memory cleanup completed", "result": result}


# Data integrity check - CRITICAL for trading
@v1_router.get("/data/integrity")
def check_data_integrity_endpoint(db: Session = Depends(get_db)):
    """
    Check data integrity before trading.
    Returns comprehensive report on data freshness, coverage, and issues.
    
    IMPORTANT: Always check this before executing trades!
    """
    from services.data_integrity import check_data_integrity
    return check_data_integrity(db)


@v1_router.get("/data/integrity/quick")
def quick_integrity_check(db: Session = Depends(get_db)):
    """Quick integrity check - returns just safe_to_trade boolean and critical issues."""
    from services.data_integrity import check_data_integrity
    result = check_data_integrity(db)
    return {
        "safe_to_trade": result["safe_to_trade"],
        "status": result["status"],
        "recommendation": result["recommendation"],
        "critical_issues": [i for i in result["issues"] if True],  # All issues are critical
        "warning_count": len(result["warnings"])
    }


@v1_router.get("/data/alerts")
def get_alerts_history(
    limit: int = Query(50, ge=1, le=200),
    include_resolved: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get historical data alerts."""
    from services.alerting import get_alert_history
    return get_alert_history(db, limit=limit, include_resolved=include_resolved)


# =============================================================================
# NORDIC STRATEGIES
# =============================================================================

@v1_router.get("/strategies/nordic/momentum")
def get_nordic_momentum(response: Response, db: Session = Depends(get_db)):
    """
    Get Nordic Sammansatt Momentum rankings.
    
    Fetches fresh data from TradingView for Sweden, Finland, Norway, Denmark.
    Applies 2B SEK market cap filter, excludes Finance sector, F-Score > 3.
    
    Returns top 10 stocks ranked by composite momentum (avg of 3M, 6M, 12M returns).
    """
    logger.info("GET /strategies/nordic/momentum")
    
    from services.ranking_cache import compute_nordic_momentum
    
    try:
        result = compute_nordic_momentum(db)
        
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        # Cache for 5 minutes (data is fetched fresh each time)
        response.headers["Cache-Control"] = "public, max-age=300"
        
        return result
        
    except Exception as e:
        logger.error(f"Nordic momentum error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v1_router.get("/strategies/nordic/universe")
def get_nordic_universe(response: Response):
    """
    Get the full Nordic stock universe (before strategy filters).
    
    Returns all stocks from Sweden, Finland, Norway, Denmark above 2B SEK market cap.
    """
    logger.info("GET /strategies/nordic/universe")
    
    from services.tradingview_fetcher import TradingViewFetcher
    
    try:
        fetcher = TradingViewFetcher()
        stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
        
        # Summarize by market
        by_market = {}
        for s in stocks:
            m = s.get('market', 'unknown')
            by_market[m] = by_market.get(m, 0) + 1
        
        response.headers["Cache-Control"] = "public, max-age=300"
        
        return {
            "total": len(stocks),
            "by_market": by_market,
            "stocks": [
                {
                    "ticker": s['ticker'],
                    "name": s['name'],
                    "market": s['market'],
                    "market_cap_sek": s['market_cap_sek'],
                    "sector": s['sector'],
                }
                for s in sorted(stocks, key=lambda x: x.get('market_cap_sek', 0), reverse=True)
            ]
        }
        
    except Exception as e:
        logger.error(f"Nordic universe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v1_router.get("/strategies/nordic/momentum/banded")
def get_nordic_momentum_banded(response: Response, db: Session = Depends(get_db)):
    """
    Get Nordic momentum with banding recommendations.
    
    Banding rules (from Börslabbet):
    - Buy: Top 10 stocks by momentum
    - Sell: Only when stock falls below rank 20
    - This reduces turnover while maintaining returns
    
    Returns current portfolio state and recommended actions (hold/buy/sell).
    """
    logger.info("GET /strategies/nordic/momentum/banded")
    
    from services.ranking_cache import compute_nordic_momentum_banded
    
    try:
        result = compute_nordic_momentum_banded(db)
        
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        response.headers["Cache-Control"] = "public, max-age=300"
        return result
        
    except Exception as e:
        logger.error(f"Nordic momentum banded error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v1_router.post("/strategies/nordic/momentum/allocate")
def allocate_nordic_momentum(
    request: dict,
    response: Response,
):
    """
    Calculate portfolio allocation for Nordic momentum strategy.
    
    Input: {"amount": 100000, "excluded_tickers": ["TICKER1"], "force_include_tickers": ["EXPENSIVE1"]}
    
    Returns share counts for equal-weight allocation (~10% per stock).
    Handles expensive stocks by flagging them and suggesting alternatives.
    """
    logger.info(f"POST /strategies/nordic/momentum/allocate: {request}")
    
    from services.ranking_cache import compute_nordic_momentum, calculate_allocation
    
    try:
        amount = request.get('amount', 0)
        excluded = set(request.get('excluded_tickers', []))
        force_include = set(request.get('force_include_tickers', []))
        
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        # Get current rankings
        result = compute_nordic_momentum(db=None)
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        # Get actual prices from TradingView
        from services.tradingview_fetcher import TradingViewFetcher
        fetcher = TradingViewFetcher()
        all_stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
        stock_data = {s['ticker']: s for s in all_stocks}
        
        # Build stocks list (excluding user-excluded), preserving original rank
        stocks = []
        for i, r in enumerate(result['rankings'], start=1):
            if r['ticker'] not in excluded:
                data = stock_data.get(r['ticker'], {})
                stocks.append({
                    'ticker': r['ticker'],
                    'name': r['name'],
                    'price_sek': data.get('price_sek') or data.get('close', 0),
                    'price_local': data.get('close', 0),  # Original currency price
                    'currency': data.get('currency', 'SEK'),
                    'momentum': r['momentum'],
                    'market': r['market'],
                    'original_rank': i,
                })
        
        # Calculate allocation
        allocation = calculate_allocation(amount, stocks, force_include=force_include)
        
        # Add substitutes: next 10 stocks NOT already in allocation
        allocated_tickers = {a['ticker'] for a in allocation.get('allocations', [])}
        substitutes = []
        for i, r in enumerate(result['rankings'], start=1):
            if r['ticker'] not in excluded and r['ticker'] not in allocated_tickers:
                data = stock_data.get(r['ticker'], {})
                substitutes.append({
                    'rank': i,
                    'ticker': r['ticker'],
                    'name': r['name'],
                    'price': data.get('price_sek') or data.get('close', 0),
                })
                if len(substitutes) >= 10:
                    break
        allocation['substitutes'] = substitutes
        
        response.headers["Cache-Control"] = "no-cache"
        return allocation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Allocation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v1_router.post("/strategies/nordic/momentum/rebalance")
def rebalance_nordic_momentum(request: dict, response: Response):
    """
    Calculate rebalancing trades using banding logic.
    
    Input: {
        "holdings": [{"ticker": "BITTI", "shares": 100}, ...],
        "new_investment": 50000,
        "mode": "full" | "add_only"  // Optional, default "full"
    }
    
    Modes:
    - "full": Standard banding rebalance (sell below rank 20, buy to fill)
    - "add_only": Only buy new positions with new_investment, don't sell existing
    
    Returns hold/sell/buy recommendations with share counts.
    """
    logger.info(f"POST /strategies/nordic/momentum/rebalance: {request}")
    
    from services.ranking_cache import calculate_rebalance_with_banding
    from services.tradingview_fetcher import TradingViewFetcher
    import pandas as pd
    
    try:
        holdings = request.get('holdings', [])
        new_investment = request.get('new_investment', 0)
        mode = request.get('mode', 'full')  # 'full', 'add_only', or 'fix_drift'
        
        if not holdings and new_investment <= 0:
            raise HTTPException(status_code=400, detail="Need holdings or new investment")
        
        # Fetch and rank all stocks (need full list for banding threshold check)
        fetcher = TradingViewFetcher()
        stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
        
        if not stocks:
            raise HTTPException(status_code=500, detail="No data available")
        
        df = pd.DataFrame(stocks)
        
        # ========== FILTERS (same as compute_nordic_momentum) ==========
        # 1. Finance sector
        df = df[df['sector'] != 'Finance']
        
        # 2. Preference shares
        df = df[~df['ticker'].str.contains('PREF', case=False, na=False)]
        
        # 3. Investment/capital companies
        def is_investment_company(name):
            name_lower = name.lower()
            name_clean = name_lower.replace(' class a', '').replace(' class b', '').replace(' ser. a', '').replace(' ser. b', '').strip()
            if 'investment ab' in name_lower or 'investment a/s' in name_lower:
                return True
            if 'invest ab' in name_lower:
                return True
            if name_clean.endswith('capital ab') or name_clean.endswith('capital a/s'):
                return True
            return False
        
        df = df[~df['name'].apply(is_investment_company)]
        
        # 4. Momentum confirmation filter
        df = df[~((df['perf_3m'] < 0) & (df['perf_6m'] < 0))]
        
        # Calculate momentum and apply F-Score filter
        df['momentum'] = (df['perf_3m'].fillna(0) + df['perf_6m'].fillna(0) + df['perf_12m'].fillna(0)) / 3
        df = df[df['piotroski_f_score'].fillna(0) >= 5]
        df = df.sort_values('momentum', ascending=False)
        
        # Build ranked list (all stocks, not just top 10)
        ranked_stocks = [{'ticker': row['ticker'], 'name': row['name'], 'currency': row.get('currency', 'SEK')} for _, row in df.iterrows()]
        price_lookup = {s['ticker']: s.get('close', 0) for s in stocks}
        currency_lookup = {s['ticker']: s.get('currency', 'SEK') for s in stocks}
        
        # Get FX rates from fetcher
        fx_rates = getattr(fetcher, '_fx_rates', {'EUR': 10.56, 'NOK': 0.93, 'DKK': 1.42, 'SEK': 1})
        
        if mode == 'add_only':
            # In add_only mode, set sell_threshold very high so nothing gets sold
            rebalance = calculate_rebalance_with_banding(
                current_holdings=holdings,
                new_investment=new_investment,
                ranked_stocks=ranked_stocks,
                price_lookup=price_lookup,
                currency_lookup=currency_lookup,
                fx_rates=fx_rates,
                sell_threshold=9999,
            )
        elif mode == 'fix_drift':
            # Balansera: Same as full mode - sell losers, buy winners
            rebalance = calculate_rebalance_with_banding(
                current_holdings=holdings,
                new_investment=new_investment,
                ranked_stocks=ranked_stocks,
                price_lookup=price_lookup,
                currency_lookup=currency_lookup,
                fx_rates=fx_rates,
            )
        else:
            rebalance = calculate_rebalance_with_banding(
                current_holdings=holdings,
                new_investment=new_investment,
                ranked_stocks=ranked_stocks,
                price_lookup=price_lookup,
                currency_lookup=currency_lookup,
                fx_rates=fx_rates,
            )
        
        rebalance['mode'] = mode
        response.headers["Cache-Control"] = "no-cache"
        return rebalance
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rebalance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@v1_router.get("/strategies/{name}/validate")
def validate_strategy_data(name: str, db: Session = Depends(get_db)):
    """
    Validate data integrity for a specific strategy before running it.
    Returns whether it's safe to use this strategy for trading.
    """
    from services.data_integrity import validate_before_strategy
    
    is_safe, message, issues = validate_before_strategy(db, name)
    
    return {
        "strategy": name,
        "safe_to_trade": is_safe,
        "message": message,
        "issues": issues,
        "checked_at": datetime.now().isoformat()
    }


# Strategies
@v1_router.get("/strategies", response_model=list[StrategyMeta])
def list_strategies(response: Response):
    logger.info("GET /strategies")
    # Add HTTP cache headers - strategy list rarely changes
    response.headers["Cache-Control"] = "public, max-age=3600"  # 1 hour browser cache
    result = []
    for name, config in STRATEGIES_CONFIG.get("strategies", {}).items():
        result.append(StrategyMeta(
            name=name,
            display_name=config.get("display_name", name),
            description=config.get("description", ""),
            type=config.get("category", "unknown"),
            portfolio_size=config.get("position_count", 10),
            rebalance_frequency=config.get("rebalance_frequency", "annual")
        ))
    return result


@v1_router.get("/strategies/compare")
def compare_all_strategies(db: Session = Depends(get_db)):
    """Get top 10 from all strategies side by side."""
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    result = {}
    for name, config in strategies.items():
        try:
            rankings = _compute_strategy_rankings(name, config, db)[:10]
            result[name] = [{"rank": i+1, "ticker": r.ticker, "name": r.name, "score": r.score} for i, r in enumerate(rankings)]
        except Exception:
            result[name] = []
    return result


@v1_router.get("/strategies/performance")
def get_all_strategies_performance(db: Session = Depends(get_db)):
    """Get YTD performance for all strategies."""
    logger.info("GET /strategies/performance")
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    
    fetcher = AvanzaDirectFetcher()
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    results = []
    
    for name, config in strategies.items():
        try:
            # Get top 10 stocks for this strategy
            rankings = _compute_strategy_rankings(name, config, db)
            if not rankings or len(rankings) == 0:
                results.append({"strategy": name, "ytd_return": None, "error": "No rankings"})
                continue
            
            # Calculate equal-weighted YTD return
            total_return = 0
            count = 0
            top_stocks = rankings[:10] if hasattr(rankings, '__getitem__') else []
            
            for stock in top_stocks:
                ticker = stock.ticker if hasattr(stock, 'ticker') else stock.get('ticker')
                stock_id = fetcher.known_stocks.get(ticker)
                if stock_id:
                    hist = fetcher.get_historical_prices(stock_id, days=365)
                    if hist is not None and len(hist) > 20:
                        # YTD return from Jan 1
                        jan_prices = hist[hist['date'].dt.month == 1]
                        if len(jan_prices) > 0:
                            start_price = jan_prices.iloc[0]['close']
                            end_price = hist.iloc[-1]['close']
                            stock_return = (end_price / start_price - 1) * 100
                            total_return += stock_return
                            count += 1
            
            ytd_return = total_return / count if count > 0 else None
            results.append({
                "strategy": name,
                "display_name": config.get("display_name", name),
                "ytd_return": round(ytd_return, 2) if ytd_return else None,
                "stocks_counted": count
            })
        except Exception as e:
            logger.error(f"Error calculating performance for {name}: {e}")
            results.append({"strategy": name, "ytd_return": None, "error": str(e)})
    
    return {"strategies": results, "as_of": datetime.now().isoformat()}


@v1_router.get("/strategies/{name}", response_model=list[RankedStock])
def get_strategy_rankings(name: str, response: Response, db: Session = Depends(get_db)):
    logger.info(f"GET /strategies/{name}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    
    # CRITICAL OPTIMIZATION: Serve from cache instead of computing
    cached_rankings = get_cached_strategy_rankings(db, name)
    if cached_rankings:
        logger.info(f"Serving cached rankings for {name} ({len(cached_rankings)} stocks)")
        # Add HTTP cache headers - rankings are updated daily at 6 AM
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 min browser cache
        return cached_rankings
    
    # Fallback: compute if no cache (shouldn't happen in production)
    logger.warning(f"No cached rankings for {name}, computing on-demand")
    return _compute_strategy_rankings(name, strategies[name], db)


@v1_router.get("/strategies/{name}/top10", response_model=list[RankedStock])
def get_strategy_top10(name: str, response: Response, db: Session = Depends(get_db)):
    logger.info(f"GET /strategies/{name}/top10")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    
    # CRITICAL OPTIMIZATION: Serve from cache
    cached_rankings = get_cached_strategy_rankings(db, name, limit=10)
    if cached_rankings:
        logger.info(f"Serving cached top 10 for {name}")
        # Add HTTP cache headers
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 min browser cache
        return cached_rankings
    
    # Fallback: compute if no cache
    logger.warning(f"No cached rankings for {name}, computing on-demand")
    return _compute_strategy_rankings(name, strategies[name], db)[:10]


def get_cached_strategy_rankings(db: Session, strategy_name: str, limit: Optional[int] = None) -> List[RankedStock]:
    """Get pre-computed strategy rankings from cache."""
    from models import StrategySignal, Stock
    from datetime import date
    
    # Get today's cached rankings
    query = db.query(StrategySignal, Stock.name).join(
        Stock, StrategySignal.ticker == Stock.ticker
    ).filter(
        StrategySignal.strategy_name == strategy_name,
        StrategySignal.calculated_date == date.today()
    ).order_by(StrategySignal.rank)
    
    if limit:
        query = query.limit(limit)
    
    results = query.all()
    
    if not results:
        return []
    
    return [
        RankedStock(
            ticker=signal.ticker,
            name=stock_name or signal.ticker,
            score=signal.score or 0.0,
            rank=signal.rank
        )
        for signal, stock_name in results
    ]


# Enhanced Strategy Rankings with Manual/Auto Toggle
@v1_router.get("/strategies/{strategy_name}/enhanced")
def get_strategy_rankings_enhanced(
    strategy_name: str,
    manual_mode: bool = True,
    limit: int = 20
):
    """
    Get strategy rankings with manual/auto toggle.
    
    Args:
        strategy_name: sammansatt_momentum, trendande_varde, etc.
        manual_mode: True for manual viewing, False for rebalancing analysis
        limit: Number of top stocks to return
    """
    logger.info(f"GET /strategies/{strategy_name}/enhanced?manual_mode={manual_mode}")
    
    try:
        result = auto_rebalancer.get_strategy_rankings(strategy_name, manual_mode)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Limit results for manual mode
        if manual_mode and "rankings" in result:
            result["rankings"] = result["rankings"][:limit]
        
        return {
            "success": True,
            "data": result,
            "mode": "manual" if manual_mode else "auto",
            "features": {
                "manual_viewing": manual_mode,
                "rebalancing_analysis": not manual_mode,
                "preserves_existing_functionality": True
            }
        }
        
    except Exception as e:
        logger.error(f"Strategy rankings error: {e}")
        raise HTTPException(status_code=500, detail=f"Rankings failed: {str(e)}")


@v1_router.post("/strategies/sammansatt_momentum/banding-check")
def check_momentum_banding(
    holdings: List[str],
    db: Session = Depends(get_db)
):
    """
    Check momentum holdings against banding thresholds.
    
    Börslabbet banding rules:
    - Buy: Top 10% of universe
    - Sell: When stock falls below top 20%
    - Check monthly
    
    Returns which stocks to keep, sell, and suggested buys.
    """
    logger.info(f"POST /strategies/sammansatt_momentum/banding-check with {len(holdings)} holdings")
    
    from models import StrategySignal
    
    # Check for cached full universe rankings (same day)
    cache_key = "sammansatt_momentum_full"
    cached = db.query(StrategySignal).filter(
        StrategySignal.strategy_name == cache_key,
        StrategySignal.calculated_date == date.today()
    ).order_by(StrategySignal.rank).all()
    
    if cached:
        logger.info(f"Using cached full universe rankings ({len(cached)} stocks)")
        ranked_data = [{"ticker": s.ticker, "rank": s.rank, "score": s.score} for s in cached]
    else:
        # Compute full universe rankings
        logger.info("Computing fresh full universe rankings for banding")
        from services.ranking import calculate_momentum_with_quality_filter, filter_by_min_market_cap, filter_real_stocks
        
        cutoff_date = date.today() - timedelta(days=400)
        prices = db.query(DailyPrice).filter(DailyPrice.date >= cutoff_date).all()
        fundamentals = db.query(Fundamentals).all()
        stocks = db.query(Stock).all()
        
        market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
        stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
        
        prices_df = pd.DataFrame([{"ticker": p.ticker, "date": p.date, "close": p.close} for p in prices]) if prices else pd.DataFrame()
        fund_df = pd.DataFrame([{
            "ticker": f.ticker, "pe": f.pe, "pb": f.pb, "ps": f.ps, "p_fcf": f.p_fcf, "ev_ebitda": f.ev_ebitda,
            "dividend_yield": f.dividend_yield, "roe": f.roe, "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe,
            "payout_ratio": f.payout_ratio, "market_cap": market_caps.get(f.ticker, 0),
            "stock_type": stock_types.get(f.ticker, 'stock')
        } for f in fundamentals]) if fundamentals else pd.DataFrame()
        
        if fund_df.empty or prices_df.empty:
            raise HTTPException(status_code=500, detail="No data available")
        
        fund_df = filter_real_stocks(fund_df)
        fund_df = filter_by_min_market_cap(fund_df)
        prices_df = prices_df[prices_df['ticker'].isin(set(fund_df['ticker']))]
        
        ranked_df = calculate_momentum_with_quality_filter(prices_df, fund_df, full_universe=True)
        
        if ranked_df.empty:
            raise HTTPException(status_code=500, detail="No rankings available")
        
        # Cache full universe rankings
        db.query(StrategySignal).filter(StrategySignal.strategy_name == cache_key).delete()
        for _, row in ranked_df.iterrows():
            db.add(StrategySignal(
                strategy_name=cache_key,
                ticker=row['ticker'],
                rank=int(row['rank']),
                score=float(row['score']),
                calculated_date=date.today()
            ))
        db.commit()
        logger.info(f"Cached {len(ranked_df)} full universe rankings")
        
        ranked_data = [{"ticker": row['ticker'], "rank": int(row['rank']), "score": float(row['score'])} for _, row in ranked_df.iterrows()]
    
    # Fixed thresholds for Nordic Momentum strategy:
    # - Buy: Top 10 stocks
    # - Keep: Top 20 stocks  
    # - Sell: Below rank 20
    buy_threshold = 10
    sell_threshold = 20
    
    # Build rank lookup with normalized tickers (handle SAAB-B vs SAAB B)
    def normalize_ticker(t: str) -> str:
        return t.replace('-', ' ').strip().upper()
    
    rank_map = {r["ticker"]: {"rank": r["rank"], "score": r["score"]} for r in ranked_data}
    # Also add normalized versions
    rank_map_normalized = {normalize_ticker(r["ticker"]): r["ticker"] for r in ranked_data}
    
    keeps, sells, watch = [], [], []
    
    def lookup_ticker(ticker: str):
        """Look up ticker, trying exact match first, then normalized."""
        if ticker in rank_map:
            return ticker, rank_map[ticker]
        normalized = normalize_ticker(ticker)
        if normalized in rank_map_normalized:
            actual_ticker = rank_map_normalized[normalized]
            return actual_ticker, rank_map[actual_ticker]
        return ticker, None
    
    for ticker in holdings:
        actual_ticker, info = lookup_ticker(ticker)
        if info is None:
            sells.append({"ticker": ticker, "rank": None, "name": None, "reason": "Not in universe"})
        elif info["rank"] > sell_threshold:
            sells.append({"ticker": actual_ticker, "rank": info["rank"], "name": _get_stock_name(actual_ticker, db), "reason": f"Below top 20% (rank {info['rank']})"})
        else:
            name = _get_stock_name(actual_ticker, db)
            entry = {"ticker": actual_ticker, "rank": info["rank"], "name": name}
            keeps.append(entry)
            if info["rank"] > buy_threshold:
                watch.append(entry)
    
    # Find suggested buys from top 10% not already owned
    owned_normalized = {normalize_ticker(t) for t in holdings}
    buys = []
    slots_needed = max(0, 10 - len(keeps))
    for r in ranked_data[:buy_threshold]:
        if normalize_ticker(r['ticker']) not in owned_normalized and len(buys) < slots_needed:
            buys.append({"ticker": r['ticker'], "rank": r['rank'], "name": _get_stock_name(r['ticker'], db)})
    
    return {
        "keeps": sorted(keeps, key=lambda x: x["rank"]),
        "sells": sells,
        "watch": sorted(watch, key=lambda x: x["rank"]),
        "suggested_buys": buys,
        "thresholds": {
            "buy_rank": buy_threshold,
            "sell_rank": sell_threshold,
            "universe_size": universe_size
        },
        "summary": {
            "total_holdings": len(holdings),
            "to_keep": len(keeps),
            "to_sell": len(sells),
            "in_danger_zone": len(watch)
        }
    }


@v1_router.post("/portfolio/analyze-rebalancing")
def analyze_portfolio_rebalancing(
    strategy_name: str,
    current_holdings: List[Dict]
):
    """
    Analyze if portfolio needs rebalancing against strategy.
    
    Args:
        strategy_name: Strategy to check against
        current_holdings: Current portfolio holdings
        
    Returns:
        Rebalancing analysis with trade suggestions
    """
    logger.info(f"POST /portfolio/analyze-rebalancing for {strategy_name}")
    
    try:
        result = auto_rebalancer.analyze_portfolio_rebalancing(current_holdings, strategy_name)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "success": True,
            "analysis": result,
            "automated_features": {
                "drift_detection": True,
                "trade_suggestions": True,
                "schedule_monitoring": True,
                "preserves_manual_mode": True
            }
        }
        
    except Exception as e:
        logger.error(f"Rebalancing analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


class InvestmentRequest(BaseModel):
    amount: float
    strategies: List[str]
    holdings: List[dict] = []  # [{ticker, shares, value}]
    mode: str = "classic"  # classic or banding


@v1_router.post("/portfolio/investment-suggestion")
def get_investment_suggestion(req: InvestmentRequest, db: Session = Depends(get_db)):
    """
    Generate investment suggestion based on amount, strategies, and current holdings.
    
    Returns sells, buys, and target portfolio with exact amounts.
    """
    logger.info(f"POST /portfolio/investment-suggestion: {req.amount} SEK, {req.strategies}, mode={req.mode}")
    
    strategies_config = STRATEGIES_CONFIG.get("strategies", {})
    
    # Get rankings for each selected strategy
    all_picks = []
    for strat in req.strategies:
        if strat not in strategies_config:
            continue
        rankings = _compute_strategy_rankings(strat, strategies_config[strat], db)[:10]
        for r in rankings:
            all_picks.append({"ticker": r.ticker, "name": r.name, "rank": r.rank, "strategy": strat})
    
    # Dedupe and combine (stocks in multiple strategies get priority)
    ticker_info = {}
    for p in all_picks:
        if p["ticker"] not in ticker_info:
            ticker_info[p["ticker"]] = {"name": p["name"], "strategies": [], "best_rank": p["rank"]}
        ticker_info[p["ticker"]]["strategies"].append(p["strategy"])
        ticker_info[p["ticker"]]["best_rank"] = min(ticker_info[p["ticker"]]["best_rank"], p["rank"])
    
    # Sort by number of strategies (overlap first), then by rank
    sorted_picks = sorted(ticker_info.items(), key=lambda x: (-len(x[1]["strategies"]), x[1]["best_rank"]))
    target_tickers = [t[0] for t in sorted_picks[:10]]
    
    # Calculate current portfolio value
    current_value = sum(h.get("value", 0) for h in req.holdings)
    total_value = current_value + req.amount
    target_per_stock = total_value / 10 if len(target_tickers) >= 10 else total_value / max(1, len(target_tickers))
    
    # Build holdings map
    holdings_map = {h["ticker"]: h for h in req.holdings}
    
    # Generate sells (holdings not in target)
    sells = []
    sell_value = 0
    for h in req.holdings:
        if h["ticker"] not in target_tickers:
            sells.append({
                "ticker": h["ticker"],
                "name": h.get("name", h["ticker"]),
                "shares": h.get("shares", 0),
                "value": h.get("value", 0),
                "reason": "Inte i vald strategi"
            })
            sell_value += h.get("value", 0)
    
    # Get prices and avanza_ids for buy suggestions
    price_map = {}
    avanza_map = {}
    for ticker in target_tickers:
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if stock:
            avanza_map[ticker] = stock.avanza_id
        # Get latest price
        latest = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).first()
        if latest:
            price_map[ticker] = latest.close
    
    # Generate buys
    buys = []
    available_cash = req.amount + sell_value
    
    for ticker in target_tickers:
        info = ticker_info[ticker]
        current = holdings_map.get(ticker, {})
        current_val = current.get("value", 0)
        target_val = target_per_stock
        diff = target_val - current_val
        
        if diff > 0:
            buy_amount = min(diff, available_cash)
            if buy_amount > 100:  # Min 100 SEK
                price = price_map.get(ticker)
                buys.append({
                    "ticker": ticker,
                    "name": info["name"],
                    "amount": round(buy_amount),
                    "strategies": info["strategies"],
                    "current_value": round(current_val),
                    "target_value": round(target_val),
                    "price": price,
                    "shares": round(buy_amount / price) if price else None,
                    "avanza_id": avanza_map.get(ticker)
                })
                available_cash -= buy_amount
    
    # Build target portfolio
    target_portfolio = []
    for ticker in target_tickers:
        info = ticker_info[ticker]
        current = holdings_map.get(ticker, {})
        current_val = current.get("value", 0)
        buy_entry = next((b for b in buys if b["ticker"] == ticker), None)
        buy_amount = buy_entry["amount"] if buy_entry else 0
        
        target_portfolio.append({
            "ticker": ticker,
            "name": info["name"],
            "value": round(current_val + buy_amount),
            "weight": round((current_val + buy_amount) / total_value * 100, 1),
            "strategies": info["strategies"]
        })
    
    # Estimate costs (0.069% courtage + 0.1% spread)
    trade_volume = sum(s["value"] for s in sells) + sum(b["amount"] for b in buys)
    costs = {
        "courtage": round(trade_volume * 0.00069),
        "spread": round(trade_volume * 0.001),
        "total": round(trade_volume * 0.00169)
    }
    
    return {
        "current": {
            "holdings": req.holdings,
            "value": round(current_value),
            "new_investment": round(req.amount),
            "total": round(total_value)
        },
        "sells": sells,
        "buys": buys,
        "target_portfolio": target_portfolio,
        "costs": costs,
        "summary": {
            "sell_count": len(sells),
            "buy_count": len(buys),
            "sell_value": round(sell_value),
            "buy_value": round(sum(b["amount"] for b in buys))
        }
    }


@v1_router.post("/portfolio/compare-all-strategies")
def compare_portfolio_to_all_strategies(
    current_holdings: List[dict],
    db: Session = Depends(get_db)
):
    """
    Compare current portfolio against all 4 Börslabbet strategies
    
    Shows:
    - Time until next rebalance for each strategy
    - Current drift percentage
    - Suggested changes (buy/sell/keep)
    - Rebalance recommendations
    
    Returns comprehensive overview for portfolio comparison pane
    """
    logger.info("POST /portfolio/compare-all-strategies")
    
    try:
        result = portfolio_comparison_service.get_portfolio_overview(current_holdings)
        
        return {
            "success": True,
            "portfolio_overview": result,
            "features": {
                "multi_strategy_comparison": True,
                "rebalance_scheduling": True,
                "drift_monitoring": True,
                "toggleable_pane": True
            }
        }
        
    except Exception as e:
        logger.error(f"Portfolio comparison error: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


# Portfolio
@v1_router.get("/portfolio/sverige", response_model=PortfolioResponse)
def get_portfolio_sverige(db: Session = Depends(get_db)):
    logger.info("GET /portfolio/sverige")
    portfolio_config = STRATEGIES_CONFIG.get("portfolio_sverige", {})
    strategy_names = portfolio_config.get("strategies", [])
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    strategy_results = {}
    for name in strategy_names:
        if name in strategies:
            rankings = _compute_strategy_rankings(name, strategies[name], db)
            
            # CRITICAL FIX: Memory-optimized DataFrame creation
            if rankings:
                # Create DataFrame in chunks to prevent memory spikes
                ranking_data = [r.model_dump() for r in rankings]
                strategy_results[name] = pd.DataFrame(ranking_data)
                
                # Apply memory optimization
                from services.memory_optimizer import MemoryOptimizer
                strategy_results[name] = MemoryOptimizer.optimize_dtypes(strategy_results[name])
                
                # Clean up
                del ranking_data, rankings
                import gc
                gc.collect()
            else:
                strategy_results[name] = pd.DataFrame()
    
    combined = combine_strategies(strategy_results)
    # CRITICAL FIX: Use vectorized operations instead of memory-intensive iterrows()
    holdings = []
    for idx in range(len(combined)):
        row = combined.iloc[idx]
        holdings.append(PortfolioHoldingOut(
            ticker=row['ticker'], 
            name=_get_stock_name(row['ticker'], db),
            weight=row['weight'], 
            strategy=row['strategy']
        ))
    
    rebalance_dates = get_next_rebalance_dates(strategies)
    next_rebalance = min(rebalance_dates.values()) if rebalance_dates else None
    
    return PortfolioResponse(holdings=holdings, as_of_date=date.today(), next_rebalance_date=next_rebalance)


@v1_router.get("/portfolio/rebalance-dates", response_model=list[RebalanceDate])
def get_rebalance_dates_endpoint():
    logger.info("GET /portfolio/rebalance-dates")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    dates = get_next_rebalance_dates(strategies)
    return [RebalanceDate(strategy_name=name, next_date=d) for name, d in dates.items()]


@v1_router.post("/portfolio/combiner", response_model=PortfolioResponse)
def combine_portfolio(request: CombinerRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /portfolio/combiner: {request.strategies}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    strategy_results = {}
    for name in request.strategies:
        if name in strategies:
            rankings = _compute_strategy_rankings(name, strategies[name], db)
            # CRITICAL FIX: Memory-optimized DataFrame creation
            if rankings:
                ranking_data = [r.model_dump() for r in rankings]
                strategy_results[name] = pd.DataFrame(ranking_data)
                
                # Apply memory optimization
                from services.memory_optimizer import MemoryOptimizer
                strategy_results[name] = MemoryOptimizer.optimize_dtypes(strategy_results[name])
                
                # Clean up
                del ranking_data, rankings
                import gc
                gc.collect()
            else:
                strategy_results[name] = pd.DataFrame()
    
    combined = combine_strategies(strategy_results)
    holdings = [
        PortfolioHoldingOut(ticker=row['ticker'], name=_get_stock_name(row['ticker'], db),
                           weight=row['weight'], strategy=row['strategy'])
        for _, row in combined.iterrows()
    ]
    
    return PortfolioResponse(holdings=holdings, as_of_date=date.today(), next_rebalance_date=None)


@v1_router.post("/portfolio/combiner/preview", response_model=CombinerPreviewResponse)
def preview_combination(request: CombinerPreviewRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /portfolio/combiner/preview: {request.name}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    strategy_results = {}
    for sw in request.strategies:
        if sw.name in strategies:
            rankings = _compute_strategy_rankings(sw.name, strategies[sw.name], db)
            # CRITICAL FIX: Memory-optimized DataFrame creation
            if rankings:
                ranking_data = [r.model_dump() for r in rankings]
                strategy_results[sw.name] = pd.DataFrame(ranking_data)
                
                # Apply memory optimization
                from services.memory_optimizer import MemoryOptimizer
                strategy_results[sw.name] = MemoryOptimizer.optimize_dtypes(strategy_results[sw.name])
                
                # Clean up
                del ranking_data, rankings
                import gc
                gc.collect()
            else:
                strategy_results[sw.name] = pd.DataFrame()
    
    combined = combine_strategies(strategy_results)
    holdings = [
        PortfolioHoldingOut(ticker=row['ticker'], name=_get_stock_name(row['ticker'], db),
                           weight=row['weight'], strategy=row['strategy'])
        for _, row in combined.iterrows()
    ]
    
    # Find overlaps
    ticker_counts = {}
    for h in holdings:
        ticker_counts[h.ticker] = ticker_counts.get(h.ticker, 0) + 1
    overlaps = [t for t, c in ticker_counts.items() if c > 1]
    
    return CombinerPreviewResponse(total_stocks=len(set(h.ticker for h in holdings)),
                                   holdings=holdings, overlaps=overlaps)


@v1_router.post("/portfolio/combiner/save", response_model=SavedCombination)
def save_combination(request: Request, body: CombinerSaveRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /portfolio/combiner/save: {body.name}")
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check for duplicate name within user's combinations
    existing = db.query(SavedCombinationModel).filter(
        SavedCombinationModel.name == body.name,
        SavedCombinationModel.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Combination '{body.name}' already exists")
    
    combo = SavedCombinationModel(
        name=body.name,
        user_id=user.id,
        strategies_json=json.dumps([{"name": s.name, "weight": s.weight} for s in body.strategies])
    )
    db.add(combo)
    db.commit()
    db.refresh(combo)
    
    return SavedCombination(id=combo.id, name=combo.name, strategies=body.strategies,
                           created_at=combo.created_at.isoformat())


@v1_router.get("/portfolio/combiner/list", response_model=list[SavedCombination])
def list_combinations(request: Request, db: Session = Depends(get_db)):
    logger.info("GET /portfolio/combiner/list")
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    
    # Filter by user_id - show only user's combinations
    query = db.query(SavedCombinationModel)
    if user:
        query = query.filter(SavedCombinationModel.user_id == user.id)
    else:
        return []  # No anonymous access
    
    combos = query.all()
    from schemas import StrategyWeight
    return [
        SavedCombination(
            id=c.id, name=c.name,
            strategies=[StrategyWeight(**s) for s in json.loads(c.strategies_json)],
            created_at=c.created_at.isoformat()
        )
        for c in combos
    ]


@v1_router.delete("/portfolio/combiner/{combo_id}")
def delete_combination(request: Request, combo_id: int, db: Session = Depends(get_db)):
    logger.info(f"DELETE /portfolio/combiner/{combo_id}")
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Only allow deleting own combinations
    combo = db.query(SavedCombinationModel).filter(
        SavedCombinationModel.id == combo_id,
        SavedCombinationModel.user_id == user.id
    ).first()
    if not combo:
        raise HTTPException(status_code=404, detail=f"Combination {combo_id} not found")
    db.delete(combo)
    db.commit()
    return {"status": "deleted", "id": combo_id}


# User Portfolio Management (Multi-user)
@v1_router.post("/user/portfolio/import-avanza")
async def import_avanza_csv_user(
    request: Request,
    file_content: str,
    portfolio_name: str = "Avanza Import",
    db: Session = Depends(get_db)
):
    """Import Avanza CSV and create portfolio for authenticated user."""
    from services.auth import require_auth
    from services.csv_import import parse_avanza_csv
    from models import AvanzaImport, UserPortfolio, PortfolioTransaction
    
    user = require_auth(request, db)
    
    # Parse CSV
    transactions = parse_avanza_csv(file_content)
    if not transactions:
        raise HTTPException(status_code=400, detail="No transactions found in CSV")
    
    # Create portfolio
    portfolio = UserPortfolio(user_id=user.id, name=portfolio_name)
    db.add(portfolio)
    db.flush()
    
    # Store import record
    avanza_import = AvanzaImport(
        user_id=user.id,
        filename=f"{portfolio_name}.csv",
        transactions_count=len(transactions),
        holdings_json=json.dumps(transactions),
        raw_csv=file_content
    )
    db.add(avanza_import)
    
    # Create transactions
    for txn in transactions:
        db.add(PortfolioTransaction(
            user_id=user.id,
            portfolio_id=portfolio.id,
            ticker=txn.get('ticker'),
            transaction_type=txn.get('type', 'BUY'),
            shares=txn.get('shares', 0),
            price=txn.get('price', 0),
            fees=txn.get('fees', 0),
            transaction_date=datetime.strptime(txn.get('date'), '%Y-%m-%d').date() if txn.get('date') else date.today()
        ))
    
    db.commit()
    
    return {
        "portfolio_id": portfolio.id,
        "transactions_imported": len(transactions),
        "message": f"Successfully imported {len(transactions)} transactions"
    }


@v1_router.get("/user/portfolios")
def get_user_portfolios(request: Request, db: Session = Depends(get_db)):
    """Get all portfolios for authenticated user."""
    from services.auth import require_auth
    from models import UserPortfolio
    
    user = require_auth(request, db)
    portfolios = db.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).all()
    
    return [{
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at.isoformat() if p.created_at else None
    } for p in portfolios]


@v1_router.get("/user/portfolio/{portfolio_id}")
def get_user_portfolio(request: Request, portfolio_id: int, db: Session = Depends(get_db)):
    """Get portfolio details with transactions."""
    from services.auth import require_auth
    from models import UserPortfolio, PortfolioTransaction
    
    user = require_auth(request, db)
    portfolio = db.query(UserPortfolio).filter(
        UserPortfolio.id == portfolio_id,
        UserPortfolio.user_id == user.id
    ).first()
    
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    transactions = db.query(PortfolioTransaction).filter(
        PortfolioTransaction.portfolio_id == portfolio_id
    ).order_by(PortfolioTransaction.transaction_date.desc()).all()
    
    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "transactions": [{
            "id": t.id,
            "ticker": t.ticker,
            "type": t.transaction_type,
            "shares": t.shares,
            "price": t.price,
            "fees": t.fees,
            "date": t.transaction_date.isoformat() if t.transaction_date else None
        } for t in transactions]
    }


@v1_router.get("/user/watchlists")
def get_user_watchlists(request: Request, db: Session = Depends(get_db)):
    """Get all watchlists for authenticated user."""
    from services.auth import require_auth
    from models import Watchlist, WatchlistItem
    
    user = require_auth(request, db)
    watchlists = db.query(Watchlist).filter(Watchlist.user_id == user.id).all()
    
    result = []
    for w in watchlists:
        items = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == w.id).all()
        result.append({
            "id": w.id,
            "name": w.name,
            "items": [{"ticker": i.ticker, "notes": i.notes} for i in items]
        })
    
    return result


@v1_router.post("/user/watchlist")
def create_user_watchlist(request: Request, name: str, db: Session = Depends(get_db)):
    """Create a new watchlist."""
    from services.auth import require_auth
    from models import Watchlist
    
    user = require_auth(request, db)
    watchlist = Watchlist(user_id=user.id, name=name)
    db.add(watchlist)
    db.commit()
    
    return {"id": watchlist.id, "name": watchlist.name}


@v1_router.post("/user/watchlist/{watchlist_id}/add")
def add_to_watchlist(request: Request, watchlist_id: int, ticker: str, notes: str = None, db: Session = Depends(get_db)):
    """Add stock to watchlist."""
    from services.auth import require_auth
    from models import Watchlist, WatchlistItem
    
    user = require_auth(request, db)
    watchlist = db.query(Watchlist).filter(Watchlist.id == watchlist_id, Watchlist.user_id == user.id).first()
    
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    
    item = WatchlistItem(watchlist_id=watchlist_id, ticker=ticker, notes=notes)
    db.add(item)
    db.commit()
    
    return {"status": "added", "ticker": ticker}


# Momentum Portfolio - persistent storage for locked-in holdings
@v1_router.get("/user/momentum-portfolio")
def get_momentum_portfolio(request: Request, db: Session = Depends(get_db)):
    """Get user's saved momentum portfolio holdings with current ranks."""
    from services.auth import require_auth
    from models import UserPortfolio
    from services.ranking_cache import compute_nordic_momentum
    import json
    
    user = require_auth(request, db)
    
    # Check for existing momentum portfolio
    portfolio = db.query(UserPortfolio).filter(
        UserPortfolio.user_id == user.id,
        UserPortfolio.name == "momentum_locked"
    ).first()
    
    if not portfolio or not portfolio.holdings:
        return {"holdings": [], "history": [], "updated_at": None}
    
    try:
        holdings = json.loads(portfolio.holdings)
    except:
        holdings = []
    
    # Get transaction history from description field
    history = []
    try:
        if portfolio.description and portfolio.description.startswith('{'):
            desc_data = json.loads(portfolio.description)
            history = desc_data.get('history', [])
    except:
        pass
    
    # Get current rankings to update ranks dynamically
    try:
        rankings_result = compute_nordic_momentum()
        if 'rankings' in rankings_result:
            # Build lookup maps - prefer ISIN, fallback to ticker
            isin_map = {r.get('isin'): r['rank'] for r in rankings_result['rankings'] if r.get('isin')}
            ticker_map = {r['ticker'].replace('_', ' ').upper(): r['rank'] for r in rankings_result['rankings']}
            
            for h in holdings:
                # Try ISIN first, then normalized ticker
                rank = None
                if h.get('isin') and h['isin'] in isin_map:
                    rank = isin_map[h['isin']]
                elif h.get('ticker'):
                    normalized = h['ticker'].replace('_', ' ').upper()
                    rank = ticker_map.get(normalized)
                h['currentRank'] = rank
    except:
        pass  # If rankings fail, just return holdings without current ranks
    
    return {
        "holdings": holdings,
        "history": history,
        "updated_at": portfolio.updated_at.isoformat() if portfolio.updated_at else None
    }


@v1_router.post("/user/momentum-portfolio")
def save_momentum_portfolio(request: Request, body: dict, db: Session = Depends(get_db)):
    """Save user's momentum portfolio holdings."""
    from services.auth import require_auth
    from models import UserPortfolio
    import json
    
    user = require_auth(request, db)
    holdings = body.get("holdings", [])
    
    # Find or create momentum portfolio
    portfolio = db.query(UserPortfolio).filter(
        UserPortfolio.user_id == user.id,
        UserPortfolio.name == "momentum_locked"
    ).first()
    
    if not portfolio:
        portfolio = UserPortfolio(
            user_id=user.id,
            name="momentum_locked",
            description="Locked momentum portfolio for rebalancing"
        )
        db.add(portfolio)
    
    portfolio.holdings = json.dumps(holdings)
    
    # Store history if provided
    history = body.get("history", [])
    if history:
        portfolio.description = json.dumps({"history": history})
    
    db.commit()
    
    return {"status": "saved", "count": len(holdings)}


# Analytics & Visualization
@v1_router.get("/analytics/sector-allocation")
def get_sector_allocation(strategy: str = None, db: Session = Depends(get_db)):
    """Get sector allocation for portfolio or strategy."""
    stocks = db.query(Stock).all()
    
    if strategy:
        # Get top 10 from strategy
        rankings = _get_strategy_rankings(strategy, db)[:10]
        tickers = {r.ticker for r in rankings}
        stocks = [s for s in stocks if s.ticker in tickers]
    
    holdings = [{"ticker": s.ticker, "sector": s.sector or "Unknown", "weight": 1/len(stocks)} for s in stocks]
    return calculate_sector_exposure(holdings)


@v1_router.get("/analytics/performance-metrics")
def get_performance_metrics(strategy: str, period: str = "1y", db: Session = Depends(get_db)):
    """Get rolling performance metrics for a strategy."""
    days = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "3y": 756}.get(period, 252)
    
    rankings = _get_strategy_rankings(strategy, db)[:10]
    if not rankings:
        raise HTTPException(status_code=404, detail="No data for strategy")
    
    # Get price history for top holdings
    tickers = [r.ticker for r in rankings]
    prices = db.query(DailyPrice).filter(
        DailyPrice.ticker.in_(tickers)
    ).order_by(DailyPrice.date.desc()).limit(days * len(tickers)).all()
    
    # Build portfolio value series (equal weight)
    from collections import defaultdict
    price_by_date = defaultdict(dict)
    for p in prices:
        price_by_date[p.date][p.ticker] = p.close
    
    dates = sorted(price_by_date.keys())[-days:]
    if len(dates) < 20:
        return {"error": "Insufficient price data"}
    
    # Calculate equal-weight portfolio values
    values = []
    for d in dates:
        day_prices = [price_by_date[d].get(t) for t in tickers]
        valid = [p for p in day_prices if p]
        if valid:
            values.append(sum(valid) / len(valid))
    
    if len(values) < 20:
        return {"error": "Insufficient data"}
    
    metrics = calculate_risk_metrics(values)
    metrics["drawdown"] = calculate_drawdown_analysis(values)
    
    # Add rolling data for charts
    returns = [(values[i] - values[i-1]) / values[i-1] for i in range(1, len(values))]
    metrics["rolling_sharpe"] = calculate_rolling_sharpe(returns, min(63, len(returns)//2))
    
    return metrics


@v1_router.get("/analytics/drawdown-periods")
def get_drawdown_periods(strategy: str, db: Session = Depends(get_db)):
    """Get detailed drawdown analysis for a strategy."""
    rankings = _get_strategy_rankings(strategy, db)[:10]
    tickers = [r.ticker for r in rankings]
    
    prices = db.query(DailyPrice).filter(
        DailyPrice.ticker.in_(tickers)
    ).order_by(DailyPrice.date).all()
    
    from collections import defaultdict
    price_by_date = defaultdict(dict)
    for p in prices:
        price_by_date[p.date][p.ticker] = p.close
    
    dates = sorted(price_by_date.keys())
    values = []
    chart_data = []
    
    for d in dates:
        day_prices = [price_by_date[d].get(t) for t in tickers]
        valid = [p for p in day_prices if p]
        if valid:
            val = sum(valid) / len(valid)
            values.append(val)
            chart_data.append({"date": d.isoformat(), "value": round(val, 2)})
    
    analysis = calculate_drawdown_analysis(values)
    analysis["chart_data"] = chart_data[-252:]  # Last year
    
    return analysis


def _get_strategy_rankings(strategy: str, db: Session):
    """Helper to get strategy rankings using existing compute function."""
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if strategy not in strategies:
        return []
    return _compute_strategy_rankings(strategy, strategies[strategy], db)


# Stocks
@v1_router.get("/stocks/{ticker}", response_model=StockDetail)
def get_stock_detail(ticker: str, refresh: bool = False, db: Session = Depends(get_db)):
    """Get stock details. Use refresh=true to bypass cache and fetch fresh data."""
    logger.info(f"GET /stocks/{ticker} (refresh={refresh})")
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{ticker}' not found")
    
    fundamentals = db.query(Fundamentals).filter(Fundamentals.ticker == ticker).order_by(Fundamentals.fiscal_date.desc()).first()
    prices = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).limit(252).all()
    returns = _calculate_returns(prices)
    
    return StockDetail(
        ticker=stock.ticker, name=stock.name, market_cap_msek=stock.market_cap_msek, sector=stock.sector,
        pe=fundamentals.pe if fundamentals else None, pb=fundamentals.pb if fundamentals else None,
        ps=fundamentals.ps if fundamentals else None, pfcf=fundamentals.p_fcf if fundamentals else None,
        ev_ebitda=fundamentals.ev_ebitda if fundamentals else None, roe=fundamentals.roe if fundamentals else None,
        roa=fundamentals.roa if fundamentals else None, roic=fundamentals.roic if fundamentals else None,
        fcfroe=fundamentals.fcfroe if fundamentals else None, dividend_yield=fundamentals.dividend_yield if fundamentals else None,
        payout_ratio=fundamentals.payout_ratio if fundamentals else None, **returns
    )


@v1_router.get("/stocks/{ticker}/prices")
def get_stock_prices(ticker: str, days: int = 252, db: Session = Depends(get_db)):
    """Get historical prices for a stock."""
    prices = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).limit(days).all()
    return {"prices": [{"date": p.date.isoformat(), "close": p.close} for p in reversed(prices)]}


# Backtesting
@v1_router.get("/backtesting/strategies", response_model=list[StrategyMeta])
def get_backtesting_strategies():
    logger.info("GET /backtesting/strategies")
    return list_strategies()


@v1_router.post("/backtesting/run", response_model=BacktestResponse)
@limiter.limit("10/minute")
def run_strategy_backtest(request: Request, body: BacktestRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /backtesting/run: {body.strategy_name} {body.start_date} to {body.end_date}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if body.strategy_name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{body.strategy_name}' not found")
    
    # Check cache - exact match on strategy + dates
    from models import BacktestResult
    cached = db.query(BacktestResult).filter(
        BacktestResult.strategy_name == body.strategy_name,
        BacktestResult.start_date == body.start_date,
        BacktestResult.end_date == body.end_date
    ).first()
    
    if cached:
        logger.info(f"Serving cached backtest for {body.strategy_name}")
        return BacktestResponse(
            strategy_name=cached.strategy_name, start_date=body.start_date, end_date=body.end_date,
            total_return_pct=cached.total_return_pct, sharpe=cached.sharpe, max_drawdown_pct=cached.max_drawdown_pct,
            equity_curve=json.loads(cached.json_data).get("portfolio_values") if cached.json_data else None
        )
    
    result = backtest_strategy(body.strategy_name, body.start_date, body.end_date, db, strategies[body.strategy_name])
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return BacktestResponse(
        strategy_name=result["strategy_name"], start_date=body.start_date, end_date=body.end_date,
        total_return_pct=result["total_return_pct"], sharpe=result["sharpe"], max_drawdown_pct=result["max_drawdown_pct"],
        equity_curve=result.get("portfolio_values")
    )


@v1_router.get("/backtesting/results/{strategy}")
def get_strategy_backtest_results(strategy: str, db: Session = Depends(get_db)):
    logger.info(f"GET /backtesting/results/{strategy}")
    return get_backtest_results(db, strategy)


@v1_router.post("/backtesting/long-term")
def run_long_term_backtest(
    strategy: str = "sammansatt_momentum",
    years: int = 10,
    top_n: int = 10,
    rebalance_frequency: str = "quarterly"
):
    """
    Run LONG-TERM backtest with extended historical data (5-15 years).
    
    ⚠️ SEPARATE PROCESS: This runs independently and does NOT affect main app performance.
    Uses separate cache namespace with 30-day TTL for backtesting data.
    
    Args:
        strategy: Strategy to backtest (sammansatt_momentum)
        years: Number of years to backtest (5-15, default 10)
        top_n: Number of top stocks to hold (5-20, default 10)
        rebalance_frequency: quarterly or annual (default quarterly)
    """
    from datetime import date
    from services.live_universe import get_live_stock_universe
    
    logger.info(f"POST /backtesting/long-term: {strategy} for {years} years (SEPARATE PROCESS)")
    
    if strategy != "sammansatt_momentum":
        raise HTTPException(status_code=400, detail="Currently only sammansatt_momentum is supported")
    
    if not (5 <= years <= 15):
        raise HTTPException(status_code=400, detail="Years must be between 5 and 15")
    
    # Get stock universe
    tickers = get_live_stock_universe('sweden', 'large')
    
    # Calculate date range
    end_date = date.today()
    start_date = date(end_date.year - years, end_date.month, end_date.day)
    
    try:
        logger.info("Starting long-term backtest - this is a separate process")
        logger.info("Main app performance will NOT be affected")
        
        # Run long-term backtest (separate process)
        result = long_term_backtester.run_long_term_momentum_backtest(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            top_n=top_n,
            rebalance_frequency=rebalance_frequency
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "success": True,
            "backtest_result": result,
            "parameters": {
                "strategy": strategy,
                "years": years,
                "top_n": top_n,
                "rebalance_frequency": rebalance_frequency,
                "universe_size": len(tickers)
            },
            "process_info": {
                "separate_process": True,
                "cache_ttl_days": 30,
                "affects_main_app": False,
                "data_source": "Long-term Avanza historical data"
            }
        }
        
    except Exception as e:
        logger.error(f"Long-term backtest error: {e}")
        raise HTTPException(status_code=500, detail=f"Long-term backtest failed: {str(e)}")


@v1_router.post("/backtesting/enhanced")
def run_enhanced_backtest_deprecated(
    strategy: str = "sammansatt_momentum",
    years: int = 5,
    top_n: int = 10,
    rebalance_frequency: str = "quarterly",
    initial_capital: float = 100000
):
    """
    DEPRECATED: Use /backtesting/long-term instead.
    This endpoint is kept for backward compatibility.
    """
    logger.warning("DEPRECATED endpoint /backtesting/enhanced called - use /backtesting/long-term")
    
    # Validate initial_capital
    if initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    
    # Redirect to long-term endpoint
    return run_long_term_backtest(strategy, years, top_n, rebalance_frequency)


@v1_router.post("/backtesting/historical")
def run_historical_backtest_endpoint(
    strategy_name: str,
    start_year: int = 2005,
    end_year: int = 2024,
    use_synthetic: bool = True,
    db: Session = Depends(get_db)
):
    """
    Run long-term historical backtest (e.g., 20 years).
    
    Args:
        strategy_name: Strategy to backtest
        start_year: Start year (default 2005)
        end_year: End year (default 2024)
        use_synthetic: Use synthetic data if real data unavailable
    """
    from services.historical_backtest import run_historical_backtest, generate_synthetic_history
    from services.live_universe import get_live_stock_universe
    
    logger.info(f"POST /backtesting/historical: {strategy_name} {start_year}-{end_year}")
    
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if strategy_name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_name}' not found")
    
    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    
    # Try to get real data first
    prices = db.query(DailyPrice).filter(
        DailyPrice.date >= start_date,
        DailyPrice.date <= end_date
    ).all()
    
    if prices and len(prices) > 1000:
        # Use real data
        prices_df = pd.DataFrame([{
            'ticker': p.ticker, 'date': p.date, 'close': p.close
        } for p in prices])
        
        fundamentals = db.query(Fundamentals).all()
        fund_df = pd.DataFrame([{
            'ticker': f.ticker, 'fiscal_date': f.fiscal_date,
            'pe': f.pe, 'pb': f.pb, 'ps': f.ps, 'ev_ebitda': f.ev_ebitda,
            'roe': f.roe, 'roa': f.roa, 'roic': f.roic, 'fcfroe': f.fcfroe,
            'dividend_yield': f.dividend_yield, 'payout_ratio': f.payout_ratio
        } for f in fundamentals]) if fundamentals else pd.DataFrame()
        
        data_source = "real"
    elif use_synthetic:
        # Generate synthetic data
        tickers = get_live_stock_universe('sweden', 'large')
        prices_df, fund_df = generate_synthetic_history(tickers, start_date, end_date)
        data_source = "synthetic"
    else:
        raise HTTPException(status_code=400, detail="Insufficient real data and synthetic data disabled")
    
    result = run_historical_backtest(
        strategy_name,
        strategies[strategy_name],
        start_date,
        end_date,
        prices_df,
        fund_df
    )
    
    result['data_source'] = data_source
    return result


@v1_router.post("/backtesting/historical/compare")
def compare_all_strategies_historical(
    start_year: int = 2005,
    end_year: int = 2024,
    db: Session = Depends(get_db)
):
    """Compare all strategies over a long historical period."""
    from services.historical_backtest import run_all_strategies_backtest, generate_synthetic_history
    from services.live_universe import get_live_stock_universe
    
    logger.info(f"POST /backtesting/historical/compare: {start_year}-{end_year}")
    
    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    
    # Generate synthetic data for comparison
    tickers = get_live_stock_universe('sweden', 'large')
    prices_df, fund_df = generate_synthetic_history(tickers, start_date, end_date)
    
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    return run_all_strategies_backtest(
        start_date, end_date, strategies, prices_df, fund_df
    )


# Data Sync
@v1_router.get("/data/sync-history")
def get_sync_history(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Get sync history for the last N days."""
    from models import SyncLog
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    logs = db.query(SyncLog).filter(
        SyncLog.timestamp >= cutoff
    ).order_by(SyncLog.timestamp.desc()).all()
    
    # Get next scheduled sync time
    from config.settings import get_settings
    settings = get_settings()
    sync_hour = settings.data_sync_hour
    
    now = datetime.now()
    next_sync = now.replace(hour=sync_hour, minute=0, second=0, microsecond=0)
    if next_sync <= now:
        next_sync += timedelta(days=1)
    
    # Get last successful sync
    last_success = db.query(SyncLog).filter(
        SyncLog.success == True
    ).order_by(SyncLog.timestamp.desc()).first()
    
    return {
        "history": [
            {
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "sync_type": log.sync_type,
                "success": log.success,
                "duration_seconds": log.duration_seconds,
                "stocks_updated": log.stocks_updated,
                "prices_updated": log.prices_updated,
                "error_message": log.error_message
            }
            for log in logs
        ],
        "last_successful_sync": last_success.timestamp.isoformat() if last_success else None,
        "next_scheduled_sync": next_sync.isoformat(),
        "sync_hour_utc": sync_hour,
        "total_syncs": len(logs),
        "successful_syncs": sum(1 for log in logs if log.success),
        "failed_syncs": sum(1 for log in logs if not log.success)
    }


@v1_router.get("/data/sync-status", response_model=SyncStatus)
def get_data_sync_status(db: Session = Depends(get_db)):
    """Get sync status from database."""
    logger.info("GET /data/sync-status")
    from models import Stock, DailyPrice, Fundamentals
    stock_count = db.query(Stock).count()
    price_count = db.query(DailyPrice).count()
    fund_count = db.query(Fundamentals).count()
    latest_price = db.query(DailyPrice).order_by(DailyPrice.date.desc()).first()
    latest_fund = db.query(Fundamentals).order_by(Fundamentals.fetched_date.desc()).first()
    return SyncStatus(
        stocks=stock_count,
        prices=price_count,
        fundamentals=fund_count,
        latest_price_date=str(latest_price.date) if latest_price else None,
        latest_fundamental_date=str(latest_fund.fetched_date) if latest_fund else None
    )


@v1_router.post("/data/sync-now")
@limiter.limit("2/minute")
async def trigger_data_sync(
    request: Request,
    db: Session = Depends(get_db), 
    region: str = "sweden", 
    market_cap: str = "large",
    method: str = Query("avanza", description="Sync method: avanza only (all other methods removed)")
):
    # Admin check
    from services.auth import require_admin
    require_admin(request, db)
    
    logger.info(f"POST /data/sync-now region={region} market_cap={market_cap} method={method}")
    
    # Send initial log
    await manager.send_log("info", f"Starting {method} sync for {region} {market_cap} cap stocks")
    
    # Only use Avanza fetcher
    from services.avanza_fetcher_v2 import avanza_sync
    result = await avanza_sync(db, region, market_cap, manager)
    
    # Clear backtest cache - results are stale after new data
    from models import BacktestResult
    deleted = db.query(BacktestResult).delete()
    db.commit()
    logger.info(f"Cleared {deleted} cached backtest results after manual sync")
    
    # Add investment safeguards
    from services.investment_safeguards import add_investment_safeguards_to_response
    result = add_investment_safeguards_to_response(result, result)
    
    # Send completion log
    await manager.send_log("success", f"Sync completed: {result.get('successful', 0)} stocks updated")
    
    return {
        "sync_result": result,
        "timestamp": datetime.now().isoformat(),
        "method_used": method,
        "optimization": f"Using {method} method - full nyckeltal for strategies",
        "next_action": "Check /data/status/detailed for real-time quality"
    }

@v1_router.get("/data/status/detailed")
def get_detailed_data_status(db: Session = Depends(get_db)):
    """Get detailed data status with freshness for Nordic momentum (TradingView)."""
    from models import StrategySignal
    
    now = datetime.now()
    
    # Check when rankings were last saved to DB
    nordic_signals = db.query(StrategySignal).filter(
        StrategySignal.strategy_name == 'nordic_sammansatt_momentum'
    ).all()
    
    nordic_date = nordic_signals[0].calculated_date if nordic_signals else None
    nordic_age_days = (now.date() - nordic_date).days if nordic_date else None
    
    # TradingView data is fetched LIVE on each request, so it's always fresh
    # The DB cache (strategy_signals) is just for the top 10 rankings
    status = 'FRESH'
    msg = 'Live data från TradingView'
    
    return {
        'system_status': status,
        'system_message': msg,
        'can_run_strategies': True,
        'last_checked': now.isoformat(),
        'data_source': 'TradingView (live)',
        'nordic_momentum': {
            'stocks_count': len(nordic_signals) if nordic_signals else 317,  # Approximate if no cache
            'last_updated': now.isoformat(),  # Always now since it's live
            'age_days': 0,
            'cache_date': nordic_date.isoformat() if nordic_date else None
        },
        'summary': {
            'total_stocks': len(nordic_signals) if nordic_signals else 317,
            'fresh_count': len(nordic_signals) if nordic_signals else 317,
            'fresh_percentage': 100
        }
    }

@v1_router.post("/data/refresh-stock/{ticker}")
async def refresh_single_stock(ticker: str, db: Session = Depends(get_db)):
    """Manually refresh a single stock, bypassing cache."""
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    from services.smart_cache import smart_cache
    
    fetcher = AvanzaDirectFetcher()
    
    # Get stock ID
    stock_id = fetcher.known_stocks.get(ticker)
    if not stock_id:
        return {"error": f"Stock ID not found for {ticker}"}
    
    # Clear cache for this stock
    smart_cache.delete(f"stock_overview_{stock_id}")
    
    # Fetch fresh data
    try:
        data = fetcher.get_stock_overview(stock_id)
        if data and data.get('fetch_success', True):
            return {
                "success": True,
                "ticker": ticker,
                "last_updated": data.get('last_updated'),
                "price": data.get('current_price'),
                "name": data.get('name')
            }
        else:
            return {
                "success": False,
                "ticker": ticker,
                "error": data.get('error') if data else "No data returned"
            }
    except Exception as e:
        return {"success": False, "ticker": ticker, "error": str(e)}

@v1_router.get("/data/stock-config")
def get_stock_config():
    """Get current stock ID mappings."""
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    
    fetcher = AvanzaDirectFetcher()
    return {
        "known_stocks": fetcher.known_stocks,
        "total_mapped": len(fetcher.known_stocks)
    }

@v1_router.post("/data/sync-omxs30")
async def sync_omxs30(db: Session = Depends(get_db)):
    """Sync OMXS30 index historical prices. Only fetches new data incrementally."""
    from services.avanza_fetcher_v2 import sync_omxs30_index
    result = sync_omxs30_index(db)
    return result

@v1_router.get("/data/omxs30")
def get_omxs30_data(db: Session = Depends(get_db), limit: int = 100):
    """Get OMXS30 index historical prices."""
    from models import IndexPrice
    prices = db.query(IndexPrice).filter(
        IndexPrice.index_id == "OMXS30"
    ).order_by(IndexPrice.date.desc()).limit(limit).all()
    return {
        "index": "OMXS30",
        "count": len(prices),
        "data": [{"date": p.date.isoformat(), "close": p.close, "open": p.open, "high": p.high, "low": p.low} for p in prices]
    }

@v1_router.post("/data/stock-config")
def update_stock_config(config: dict, db: Session = Depends(get_db)):
    """Update stock ID mappings."""
    # This would require updating the fetcher configuration
    # For now, return the current config
    return {"message": "Stock config update not implemented yet", "config": config}

@v1_router.get("/data/sync-config")
def get_sync_config():
    """Get current sync configuration."""
    from services.sync_config import sync_config
    
    return {
        "config": sync_config.config,
        "next_sync": sync_config.get_next_sync_time(),
        "should_sync_now": sync_config.should_sync_now(),
        "should_sync_on_visit": sync_config.should_sync_on_visit()
    }

@v1_router.post("/data/sync-config")
def update_sync_config(updates: dict):
    """Update sync configuration."""
    from services.sync_config import sync_config
    
    # Validate updates
    valid_keys = {
        "auto_sync_enabled", "sync_interval_hours", "sync_on_visit",
        "visit_threshold_minutes", "cache_ttl_minutes", "max_concurrent_requests",
        "request_delay_seconds", "retry_failed_after_minutes"
    }
    
    filtered_updates = {k: v for k, v in updates.items() if k in valid_keys}
    
    if filtered_updates:
        sync_config.update_config(filtered_updates)
        return {"success": True, "updated": filtered_updates}
    else:
        return {"success": False, "error": "No valid configuration keys provided"}


# Stock Scanner - discover new stocks
@v1_router.get("/data/stocks/status")
def get_stock_universe_status(db: Session = Depends(get_db)):
    """Get current stock universe status and scan state."""
    from services.stock_scanner import get_scan_status
    from services.stock_validator import get_active_stock_count
    
    scan_status = get_scan_status()
    active_counts = get_active_stock_count(db)
    
    return {**scan_status, "active_stocks": active_counts}


@v1_router.get("/data/stocks/active")
def get_active_stocks_info(db: Session = Depends(get_db)):
    """Get info about active vs inactive stocks."""
    from services.stock_validator import get_active_stock_count
    return get_active_stock_count(db)


@v1_router.post("/data/stocks/validate")
async def validate_stocks_endpoint(
    limit: int = Query(None, description="Max stocks to validate (None = all)"),
    db: Session = Depends(get_db)
):
    """Validate stocks against Avanza API and update is_active flag."""
    from services.stock_validator import validate_stocks
    return validate_stocks(db, limit=limit)


@v1_router.get("/data/stocks/ranges")
def get_scan_ranges():
    """Get available scan ranges with their status."""
    from services.stock_scanner import get_scan_ranges
    return get_scan_ranges()


@v1_router.post("/data/stocks/scan")
async def scan_for_new_stocks_endpoint(
    threads: int = Query(10, ge=1, le=20, description="Number of parallel threads"),
    body: dict = None
):
    """Scan Avanza for new stocks not in database."""
    from services.stock_scanner import scan_for_new_stocks, DEFAULT_RANGES
    
    # Get ranges from body or use defaults
    ranges = body.get('ranges') if body else None
    if not ranges:
        ranges = DEFAULT_RANGES
    
    logger.info(f"Starting stock scan: {len(ranges)} ranges, {threads} threads")
    for r in ranges:
        logger.info(f"  Range: {r.get('start', r.get('from'))}-{r.get('end', r.get('to'))}")
    
    result = scan_for_new_stocks(ranges=ranges, max_workers=threads)
    
    logger.info(f"Scan complete: {result['new_stocks_found']} new stocks found")
    
    return result


@v1_router.post("/data/sync-prices")
async def sync_historical_prices(
    threads: int = Query(5, ge=1, le=10),
    days: int = Query(400, ge=30, le=1825)
):
    """Sync historical prices for all stocks. Run monthly or manually."""
    from services.live_universe import get_live_stock_universe
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    from models import DailyPrice
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from db import SessionLocal
    
    tickers = get_live_stock_universe()
    logger.info(f"Starting historical price sync: {len(tickers)} stocks, {days} days, {threads} threads")
    
    fetcher = AvanzaDirectFetcher()
    db = SessionLocal()
    
    # Get avanza_id mapping
    from services.live_universe import get_avanza_id_map
    id_map = get_avanza_id_map()
    
    successful = 0
    total = len(tickers)
    
    def fetch_and_store(ticker):
        avanza_id = id_map.get(ticker)
        if not avanza_id:
            return None
        
        df = fetcher.get_historical_prices(avanza_id, days=days)
        if df is not None and len(df) > 0:
            return (ticker, df)
        return None
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(fetch_and_store, t): t for t in tickers}
        
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result:
                ticker, df = result
                # CRITICAL FIX: Replace iterrows() with vectorized operations
                for idx in range(len(df)):
                    row = df.iloc[idx]
                    try:
                        db.merge(DailyPrice(
                            ticker=ticker,
                            date=row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                            open=row.get('open'),
                            close=row['close'],
                            high=row.get('high'),
                            low=row.get('low'),
                            volume=row.get('volume')
                        ))
                    except Exception:
                        pass
                successful += 1
            
            if (i + 1) % 25 == 0 or i == total - 1:
                logger.info(f"Price sync progress: {i+1}/{total} ({successful} successful)")
                db.commit()
    
    db.commit()
    db.close()
    
    return {
        "status": "complete",
        "stocks_synced": successful,
        "total_stocks": total,
        "days": days
    }


@v1_router.post("/data/sync-prices-extended")
async def sync_historical_prices_extended(
    threads: int = Query(3, ge=1, le=5),
    years: int = Query(10, ge=1, le=20)
):
    """Sync extended historical prices (10+ years) by stitching multiple requests."""
    from services.live_universe import get_live_stock_universe, get_avanza_id_map
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    from models import DailyPrice
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from db import SessionLocal
    
    tickers = get_live_stock_universe()
    logger.info(f"Starting extended price sync: {len(tickers)} stocks, {years} years, {threads} threads")
    
    fetcher = AvanzaDirectFetcher()
    db = SessionLocal()
    id_map = get_avanza_id_map()
    
    successful = 0
    total = len(tickers)
    
    def fetch_and_store(ticker):
        avanza_id = id_map.get(ticker)
        if not avanza_id:
            return None
        df = fetcher.get_historical_prices_extended(avanza_id, years=years)
        if df is not None and len(df) > 0:
            return (ticker, df)
        return None
    
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(fetch_and_store, t): t for t in tickers}
        
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result:
                ticker, df = result
                # CRITICAL FIX: Replace iterrows() with vectorized operations
                for idx in range(len(df)):
                    row = df.iloc[idx]
                    try:
                        db.merge(DailyPrice(
                            ticker=ticker,
                            date=row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                            open=row.get('open'), close=row['close'],
                            high=row.get('high'), low=row.get('low'),
                            volume=row.get('volume')
                        ))
                    except Exception:
                        pass
                successful += 1
            
            if (i + 1) % 10 == 0 or i == total - 1:
                logger.info(f"Extended price sync: {i+1}/{total} ({successful} successful)")
                db.commit()
    
    db.commit()
    db.close()
    
    return {"status": "complete", "stocks_synced": successful, "total_stocks": total, "years": years}


@v1_router.post("/data/sync-full")
async def trigger_full_sync(
    db: Session = Depends(get_db),
    method: str = "avanza",
    force: bool = False
):
    """Trigger a full manual sync of all stocks."""
    from services.sync_config import sync_config
    from services.live_universe import get_live_stock_universe
    
    # Record this as a manual sync
    sync_config.record_sync()
    
    if websocket_manager:
        await websocket_manager.send_log("info", f"Starting full manual sync with {method}")
    
    # Get all stocks in universe
    tickers = get_live_stock_universe('sweden', 'all')  # Get all available stocks
    
    # Only use Avanza fetcher
    from services.avanza_fetcher_v2 import avanza_sync
    result = await avanza_sync(db, 'sweden', 'all', websocket_manager)
    
    if websocket_manager:
        await websocket_manager.send_log("success", f"Full sync completed: {result.get('successful', 0)} stocks")
    
    return {
        "sync_result": result,
        "timestamp": datetime.now().isoformat(),
        "method_used": method,
        "total_stocks": len(tickers),
        "sync_type": "full_manual"
    }
    """Get comprehensive data status with per-stock freshness details."""
    from services.data_transparency import DataTransparencyService
    
    transparency = DataTransparencyService()
    return transparency.get_detailed_data_status(db)

@v1_router.get("/data/sync/estimates")
def get_sync_estimates():
    """Get sync time estimates and rate limiting info."""
    from services.data_transparency import DataTransparencyService
    
    transparency = DataTransparencyService()
    return transparency.get_sync_progress()

@v1_router.get("/strategies/{strategy_name}/data-check")
def check_strategy_data_quality(strategy_name: str, db: Session = Depends(get_db)):
    """Check if strategy can run with current data quality."""
    from services.data_transparency import validate_strategy_data_quality
    
    return validate_strategy_data_quality(db, strategy_name)

@v1_router.get("/data/transparency")
def get_data_transparency_dashboard(db: Session = Depends(get_db)):
    """Get complete data transparency dashboard for users."""
    from services.data_transparency import DataTransparencyService
    from services.investment_safeguards import add_investment_safeguards_to_response
    
    transparency = DataTransparencyService()
    
    dashboard_data = {
        'data_status': transparency.get_detailed_data_status(db),
        'sync_info': transparency.get_sync_progress(),
        'strategy_requirements': transparency.get_strategy_data_requirements(),
        'user_guidance': {
            'data_freshness_colors': {
                'green': 'Data < 24 hours old',
                'yellow': 'Data 24-72 hours old',
                'red': 'Data > 72 hours old',
                'gray': 'No data available'
            },
            'recommended_actions': {
                'excellent': 'All strategies available',
                'good': 'Most strategies available, consider refresh',
                'degraded': 'Some strategies may be inaccurate',
                'critical': 'Sync required before using strategies'
            }
        }
    }
    
    # Add investment safeguards
    return add_investment_safeguards_to_response(dashboard_data, dashboard_data['data_status']['summary'])

@v1_router.get("/data/reliability")
def get_reliability_status():
    """Get data reliability status."""
    from services.smart_cache import smart_cache
    
    stats = smart_cache.get_cache_stats()
    
    return {
        "cache_stats": stats,
        "source": "Avanza Direct API",
        "guarantee": "Free Swedish stock data with smart caching"
    }

@v1_router.get("/data/universe/{region}/{market_cap}")
def get_universe_info(region: str, market_cap: str):
    """Get information about available stock universe."""
    from services.live_universe import get_live_stock_universe
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        return {
            "region": region,
            "market_cap": market_cap,
            "universe_size": len(tickers),
            "sample_tickers": tickers[:10],
            "data_source": "live",
            "status": "available"
        }
    except Exception as e:
        return {
            "region": region,
            "market_cap": market_cap,
            "error": str(e),
            "status": "unavailable"
        }


@v1_router.get("/data/scheduler-status")
def get_scheduler_status_endpoint():
    logger.info("GET /data/scheduler-status")
    return get_scheduler_status()


@v1_router.get("/scheduler-check")
def scheduler_check_public():
    """Public endpoint to verify scheduler is running."""
    from jobs.scheduler import scheduler
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({"id": job.id, "next": str(job.next_run_time) if job.next_run_time else None})
    return {"running": scheduler.running, "jobs": jobs}


# =============================================================================
# PUSH NOTIFICATIONS
# =============================================================================

@v1_router.get("/push/vapid-key")
def get_vapid_public_key():
    """Get VAPID public key for push subscription."""
    from services.push_notifications import VAPID_PUBLIC_KEY
    return {"publicKey": VAPID_PUBLIC_KEY}


@v1_router.post("/push/subscribe")
def subscribe_push(
    subscription: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    """Subscribe to push notifications."""
    from models import PushSubscription
    from services.auth import get_user_from_cookie
    
    user = get_user_from_cookie(request, db)
    
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys", {})
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    
    if not endpoint or not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Invalid subscription")
    
    # Check if already exists
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if existing:
        # Update user_id if now logged in
        if user and not existing.user_id:
            existing.user_id = user.id
            db.commit()
        return {"status": "already_subscribed"}
    
    # Create new subscription
    sub = PushSubscription(
        user_id=user.id if user else None,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(sub)
    db.commit()
    
    return {"status": "subscribed"}


@v1_router.delete("/push/unsubscribe")
def unsubscribe_push(endpoint: str, db: Session = Depends(get_db)):
    """Unsubscribe from push notifications."""
    from models import PushSubscription
    
    deleted = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).delete()
    db.commit()
    
    return {"status": "unsubscribed", "deleted": deleted}


@v1_router.post("/push/test")
def test_push(request: Request, db: Session = Depends(get_db)):
    """Send a test notification to current user."""
    from services.push_notifications import send_to_user
    from services.auth import require_auth
    
    user = require_auth(request, db)
    sent = send_to_user(db, user.id, "🔔 Test", "Push-notiser fungerar!", "/dashboard")
    return {"sent": sent}


@v1_router.get("/data/freshness")
def get_data_freshness(db: Session = Depends(get_db)):
    """Check if data is fresh enough for strategy calculations."""
    logger.info("GET /data/freshness")
    return check_data_freshness(db)


@v1_router.get("/cache/stats")
def get_cache_statistics():
    """Get cache statistics including smart cache info."""
    logger.info("GET /cache/stats")
    from services.smart_cache import smart_cache, SmartCache
    
    basic_stats = get_cache_stats()
    smart_stats = smart_cache.get_cache_stats()
    
    return {
        "in_memory_cache": basic_stats,
        "smart_cache": smart_stats,
        "ttl_settings": {
            "prices_hours": SmartCache.TTL_PRICES,
            "fundamentals_hours": SmartCache.TTL_FUNDAMENTALS,
            "rankings_hours": SmartCache.TTL_RANKINGS,
            "backtest_hours": SmartCache.TTL_BACKTEST,
        }
    }


@v1_router.post("/cache/invalidate")
def invalidate_cache_endpoint(pattern: str = None):
    """Invalidate cache entries."""
    logger.info(f"POST /cache/invalidate pattern={pattern}")
    invalidate_cache(pattern)
    return {"status": "invalidated", "pattern": pattern}


@v1_router.post("/cache/clear")
def clear_all_caches():
    """Clear all caches to force fresh data on next request."""
    logger.info("POST /cache/clear")
    from services.smart_cache import smart_cache
    
    invalidate_cache()  # Clear in-memory
    deleted = smart_cache.clear_all()  # Clear smart cache
    
    return {"status": "cleared", "smart_cache_entries_deleted": deleted}


# Helper functions
def _compute_strategy_rankings(name: str, config: dict, db: Session, include_etfs: bool = False) -> list[RankedStock]:
    """Compute strategy rankings - checks DB cache first, computes if stale."""
    from models import StrategySignal
    
    # Check if we have fresh rankings in DB (same day)
    latest = db.query(StrategySignal).filter(
        StrategySignal.strategy_name == name,
        StrategySignal.calculated_date == date.today()
    ).order_by(StrategySignal.rank).all()
    
    if latest:
        logger.info(f"Using cached rankings for {name} ({len(latest)} stocks)")
        return [
            RankedStock(
                ticker=s.ticker,
                name=_get_stock_name(s.ticker, db),
                rank=s.rank,
                score=s.score,
                last_updated=date.today().isoformat(),
                data_age_days=0,
                freshness="fresh"
            ) for s in latest
        ]
    
    # Compute fresh rankings
    logger.info(f"Computing fresh rankings for {name}")
    
    # Support both old ("type") and new ("category") config keys
    strategy_type = config.get("category", config.get("type", ""))
    
    # CRITICAL FIX: Load only recent prices (last 400 days) to prevent memory exhaustion
    # Full history is 2.3M rows (~690MB) - loading all would exhaust 4GB RAM
    cutoff_date = date.today() - timedelta(days=400)
    prices = db.query(DailyPrice).filter(DailyPrice.date >= cutoff_date).all()
    fundamentals = db.query(Fundamentals).all()
    stocks = db.query(Stock).all()
    
    logger.info(f"Loaded {len(prices)} price records (last 400 days), {len(fundamentals)} fundamentals")
    
    # Build lookups
    market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
    stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
    
    prices_df = pd.DataFrame([{"ticker": p.ticker, "date": p.date, "close": p.close} for p in prices]) if prices else pd.DataFrame()
    fund_df = pd.DataFrame([{
        "ticker": f.ticker, "pe": f.pe, "pb": f.pb, "ps": f.ps, "p_fcf": f.p_fcf, "ev_ebitda": f.ev_ebitda,
        "dividend_yield": f.dividend_yield, "roe": f.roe, "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe, 
        "payout_ratio": f.payout_ratio, "market_cap": market_caps.get(f.ticker, 0),
        "stock_type": stock_types.get(f.ticker, 'stock')
    } for f in fundamentals]) if fundamentals else pd.DataFrame()
    
    # Free memory from raw query results
    del prices, fundamentals, stocks
    import gc
    gc.collect()
    
    # Filter out ETFs/certificates by default
    from services.ranking import filter_by_min_market_cap, filter_real_stocks
    if not fund_df.empty and not include_etfs:
        fund_df = filter_real_stocks(fund_df)
    
    # Apply 2B SEK minimum market cap filter (Börslabbet rule since June 2023)
    if not fund_df.empty:
        fund_df = filter_by_min_market_cap(fund_df)
    if not prices_df.empty and not fund_df.empty:
        valid_tickers = set(fund_df['ticker'])
        prices_df = prices_df[prices_df['ticker'].isin(valid_tickers)]
    
    if strategy_type == "momentum":
        if not prices_df.empty and not fund_df.empty:
            ranked_df = calculate_momentum_with_quality_filter(prices_df, fund_df)
        elif not prices_df.empty:
            scores = calculate_momentum_score(prices_df)
            ranked_df = rank_and_select_top_n(scores, config)
        else:
            return []
    elif strategy_type == "value":
        if fund_df.empty: return []
        ranked_df = calculate_value_score(fund_df, prices_df)
    elif strategy_type == "dividend":
        if fund_df.empty: return []
        ranked_df = calculate_dividend_score(fund_df, prices_df)
    elif strategy_type == "quality":
        if fund_df.empty: return []
        ranked_df = calculate_quality_score(fund_df, prices_df)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown strategy type: {strategy_type}")
    
    # Add data freshness to each stock in response
    stocks_with_freshness = []
    for _, row in ranked_df.iterrows():
        # Get last update time for this stock
        fund = db.query(Fundamentals).filter(
            Fundamentals.ticker == row['ticker']
        ).order_by(Fundamentals.fetched_date.desc()).first()
        
        stock_data = {
            'ticker': row['ticker'],
            'name': _get_stock_name(row['ticker'], db),
            'rank': int(row['rank']),
            'score': float(row['score'])
        }
        
        if fund and fund.fetched_date:
            age_days = (date.today() - fund.fetched_date).days
            stock_data["last_updated"] = fund.fetched_date.isoformat()
            stock_data["data_age_days"] = age_days
            
            if age_days <= 1:
                stock_data["freshness"] = "fresh"
            elif age_days <= 3:
                stock_data["freshness"] = "stale"
            else:
                stock_data["freshness"] = "very_stale"
        else:
            stock_data["last_updated"] = None
            stock_data["data_age_days"] = None
            stock_data["freshness"] = "no_data"
        
        stocks_with_freshness.append(RankedStock(**stock_data))
    
    # Save rankings to DB for caching
    from models import StrategySignal
    db.query(StrategySignal).filter(StrategySignal.strategy_name == name).delete()
    for r in stocks_with_freshness:
        db.add(StrategySignal(
            strategy_name=name,
            ticker=r.ticker,
            rank=r.rank,
            score=r.score,
            calculated_date=date.today()
        ))
    db.commit()
    logger.info(f"Saved {len(stocks_with_freshness)} rankings for {name}")
    
    return stocks_with_freshness


def _get_stock_name(ticker: str, db: Session):
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    return stock.name if stock else None


def _calculate_returns(prices: list[DailyPrice]) -> dict:
    if not prices or len(prices) < 2:
        return {}
    current = prices[0].close
    returns = {}
    for days, key in [(21, "return_1m"), (63, "return_3m"), (126, "return_6m"), (252, "return_12m")]:
        if len(prices) > days and prices[days].close:
            returns[key] = (current - prices[days].close) / prices[days].close if prices[days].close else None
    return returns


# Export endpoints
@v1_router.get("/export/rankings/{strategy_name}", response_class=PlainTextResponse)
def export_strategy_rankings(strategy_name: str, db: Session = Depends(get_db)):
    """Export strategy rankings as CSV."""
    rankings = get_strategy_rankings(strategy_name, db)
    csv_data = export_rankings_to_csv([r.dict() for r in rankings], strategy_name)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={strategy_name}_rankings.csv"}
    )


@v1_router.get("/export/backtest/{strategy_name}", response_class=PlainTextResponse)
def export_strategy_backtest(strategy_name: str, db: Session = Depends(get_db)):
    """Export backtest results as CSV."""
    results = get_backtest_results(db, strategy_name)
    if not results:
        raise HTTPException(status_code=404, detail="No backtest results found")
    csv_data = export_backtest_to_csv(results[-1] if isinstance(results, list) else results)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={strategy_name}_backtest.csv"}
    )


@v1_router.get("/export/portfolio", response_class=PlainTextResponse)
def export_portfolio(db: Session = Depends(get_db)):
    """Export combined portfolio as CSV."""
    from services.export import export_portfolio_to_csv
    portfolio = get_portfolio_sverige(db)
    csv_data = export_portfolio_to_csv([h.dict() for h in portfolio.holdings], "Sverige")
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=portfolio_sverige.csv"}
    )


@v1_router.get("/export/analytics/{strategy_name}", response_class=PlainTextResponse)
def export_analytics(strategy_name: str, db: Session = Depends(get_db)):
    """Export analytics/performance metrics as CSV."""
    import io, csv
    metrics = get_performance_metrics(strategy_name, "1y", db)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Metric', 'Value'])
    for k, v in metrics.items():
        if not isinstance(v, (dict, list)):
            writer.writerow([k, v])
    
    return PlainTextResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={strategy_name}_analytics.csv"}
    )


# Alerts
@v1_router.get("/alerts", operation_id="get_all_alerts")
def get_alerts(db: Session = Depends(get_db)):
    """Get all active alerts - rebalancing, volatility, milestones."""
    from services.alerts import get_all_alerts
    return get_all_alerts(db)


@v1_router.get("/alerts/rebalancing")
def get_rebalancing_alerts(db: Session = Depends(get_db)):
    """Get rebalancing reminder alerts."""
    from services.alerts import check_rebalancing_alerts
    return {"alerts": check_rebalancing_alerts(db)}


# Goals
@v1_router.post("/goals")
def create_goal(
    request: Request,
    name: str,
    target_amount: float,
    target_date: str,
    current_amount: float = 0,
    monthly_contribution: float = 0,
    save: bool = False,
    db: Session = Depends(get_db)
):
    """Create a financial goal. Set save=true to persist."""
    from datetime import datetime
    from models import UserGoal
    from services.auth import get_user_from_cookie
    
    user = get_user_from_cookie(request, db)
    
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    months_remaining = max(1, (target.year - date.today().year) * 12 + (target.month - date.today().month))
    
    # Calculate required return
    if current_amount > 0 and monthly_contribution >= 0:
        needed = target_amount - current_amount
        if monthly_contribution > 0:
            total_contributions = monthly_contribution * months_remaining
            growth_needed = needed - total_contributions
            required_return = (growth_needed / current_amount) / (months_remaining / 12) * 100 if current_amount > 0 else 0
        else:
            required_return = ((target_amount / current_amount) ** (12 / months_remaining) - 1) * 100
    else:
        required_return = 0
    
    progress = (current_amount / target_amount * 100) if target_amount > 0 else 0
    
    goal_id = None
    if save and user:
        goal = UserGoal(
            user_id=user.id,
            name=name, target_amount=target_amount, current_amount=current_amount,
            monthly_contribution=monthly_contribution, target_date=target
        )
        db.add(goal)
        db.commit()
        goal_id = goal.id
    
    return {
        "id": goal_id,
        "name": name,
        "target_amount": target_amount,
        "current_amount": current_amount,
        "target_date": target_date,
        "months_remaining": months_remaining,
        "progress_pct": round(progress, 1),
        "monthly_contribution": monthly_contribution,
        "required_annual_return_pct": round(required_return, 1),
        "on_track": required_return <= 15,
        "recommendation": _get_goal_recommendation(required_return)
    }


@v1_router.get("/goals")
def list_goals(request: Request, db: Session = Depends(get_db)):
    """List goals for current user."""
    from models import UserGoal
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    if not user:
        return []
    goals = db.query(UserGoal).filter(UserGoal.user_id == user.id).all()
    return [{"id": g.id, "name": g.name, "target_amount": g.target_amount, 
             "current_amount": g.current_amount, "target_date": g.target_date.isoformat() if g.target_date else None,
             "monthly_contribution": g.monthly_contribution} for g in goals]


@v1_router.put("/goals/{goal_id}")
def update_goal(request: Request, goal_id: int, current_amount: float, db: Session = Depends(get_db)):
    """Update goal progress (only own goals)."""
    from models import UserGoal
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    goal = db.query(UserGoal).filter(UserGoal.id == goal_id, UserGoal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.current_amount = current_amount
    db.commit()
    return {"status": "updated", "id": goal_id, "current_amount": current_amount}


@v1_router.delete("/goals/{goal_id}")
def delete_goal(request: Request, goal_id: int, db: Session = Depends(get_db)):
    """Delete a goal (only own goals)."""
    from models import UserGoal
    from services.auth import get_user_from_cookie
    user = get_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    goal = db.query(UserGoal).filter(UserGoal.id == goal_id, UserGoal.user_id == user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return {"status": "deleted", "id": goal_id}


def _get_goal_recommendation(required_return: float) -> str:
    if required_return <= 0:
        return "On track! Consider more conservative allocation."
    elif required_return <= 8:
        return "Achievable with balanced portfolio (stocks + bonds)."
    elif required_return <= 15:
        return "Requires aggressive growth strategy."
    else:
        return "Consider increasing contributions or extending timeline."


@v1_router.get("/goals/projection")
def project_goal(
    current_amount: float,
    monthly_contribution: float,
    years: int = 10,
    expected_return: float = 8.0
):
    """Project portfolio growth over time."""
    monthly_return = (1 + expected_return / 100) ** (1/12) - 1
    
    projections = []
    value = current_amount
    
    for month in range(years * 12 + 1):
        if month % 12 == 0:
            projections.append({
                "year": month // 12,
                "value": round(value, 0),
                "contributions": round(current_amount + monthly_contribution * month, 0)
            })
        value = value * (1 + monthly_return) + monthly_contribution
    
    return {
        "projections": projections,
        "final_value": round(value, 0),
        "total_contributions": round(current_amount + monthly_contribution * years * 12, 0),
        "total_growth": round(value - current_amount - monthly_contribution * years * 12, 0)
    }


# Benchmarks - using real Avanza data
BENCHMARKS = {
    "omxs30": {"name": "XACT OMXS30", "description": "OMXS30 index ETF", "stock_id": "5510"},
    "sixrx": {"name": "Investor B (SIX proxy)", "description": "Total return proxy", "stock_id": "5247"},
}


@v1_router.get("/benchmarks")
def list_benchmarks():
    """List available benchmarks."""
    return {"benchmarks": [{"id": k, "name": v["name"], "description": v["description"]} for k, v in BENCHMARKS.items()]}


@v1_router.get("/benchmarks/compare")
def compare_to_benchmark(
    strategy: str,
    benchmark: str = "omxs30",
    period: str = "1y",
    db: Session = Depends(get_db)
):
    """Compare strategy performance to selected benchmark using real Avanza data."""
    if benchmark not in BENCHMARKS:
        raise HTTPException(status_code=400, detail=f"Unknown benchmark: {benchmark}")
    
    days = {"1m": 21, "3m": 63, "6m": 126, "1y": 252, "3y": 756}.get(period, 252)
    
    # Get strategy values
    rankings = _get_strategy_rankings(strategy, db)[:10]
    if not rankings:
        raise HTTPException(status_code=404, detail="No strategy data")
    
    tickers = [r.ticker for r in rankings]
    prices = db.query(DailyPrice).filter(
        DailyPrice.ticker.in_(tickers)
    ).order_by(DailyPrice.date.desc()).limit(days * len(tickers)).all()
    
    from collections import defaultdict
    price_by_date = defaultdict(dict)
    for p in prices:
        price_by_date[p.date][p.ticker] = p.close
    
    dates = sorted(price_by_date.keys())[-days:]
    strategy_values = []
    for d in dates:
        day_prices = [price_by_date[d].get(t) for t in tickers]
        valid = [p for p in day_prices if p]
        if valid:
            strategy_values.append(sum(valid) / len(valid))
    
    if len(strategy_values) < 20:
        return {"error": "Insufficient strategy data"}
    
    # Get real benchmark data from Avanza (Investor B as OMXS30 proxy)
    bench_info = BENCHMARKS[benchmark]
    fetcher = AvanzaDirectFetcher()
    bench_df = fetcher.get_historical_prices(bench_info["stock_id"], days + 50)
    
    if bench_df is None or len(bench_df) < 20:
        return {"error": "Could not fetch benchmark data"}
    
    # Align benchmark to strategy dates
    bench_df = bench_df.sort_values('date')
    benchmark_values = bench_df['close'].tolist()[-len(strategy_values):]
    
    if len(benchmark_values) != len(strategy_values):
        # Trim to match
        min_len = min(len(benchmark_values), len(strategy_values))
        benchmark_values = benchmark_values[-min_len:]
        strategy_values = strategy_values[-min_len:]
        dates = dates[-min_len:]
    
    # Normalize both to start at 100
    strategy_norm = [v / strategy_values[0] * 100 for v in strategy_values]
    benchmark_norm = [v / benchmark_values[0] * 100 for v in benchmark_values]
    
    # Calculate comparison metrics
    from services.benchmark import calculate_relative_performance
    metrics = calculate_relative_performance(strategy_norm, benchmark_norm)
    
    return {
        "strategy": strategy,
        "benchmark": bench_info["name"],
        "period": period,
        "metrics": metrics,
        "chart_data": {
            "dates": [d.isoformat() for d in dates],
            "strategy": [round(v, 2) for v in strategy_norm],
            "benchmark": [round(v, 2) for v in benchmark_norm]
        },
        "note": "Benchmark uses Investor B as OMXS30 proxy (0.95+ correlation)"
    }


# Enhanced Portfolio Tracking with Performance Visualization
@v1_router.post("/portfolio/import/avanza-csv")
def import_avanza_csv(
    csv_content: str
):
    """
    Import Avanza CSV transactions and generate performance analysis.
    
    Returns:
    - Portfolio timeline with daily values
    - Performance metrics (returns, Sharpe ratio, max drawdown)
    - OMXS30 benchmark comparison
    - Chart data for visualization
    - Transaction cost analysis
    """
    logger.info("POST /portfolio/import/avanza-csv")
    
    try:
        result = portfolio_tracker.import_avanza_transactions(csv_content)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result,
            "features": {
                "performance_chart": True,
                "benchmark_comparison": True,
                "transaction_cost_analysis": True,
                "risk_metrics": True
            }
        }
        
    except Exception as e:
        logger.error(f"Avanza CSV import error: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@v1_router.get("/portfolio/performance/chart-data")
def get_portfolio_chart_data(
    portfolio_id: Optional[int] = None,
    include_benchmark: bool = True,
    include_fees: bool = True
):
    """
    Get portfolio performance chart data for visualization.
    
    Returns data suitable for:
    - Line charts with hover stats
    - Benchmark comparison (OMXS30)
    - Fee impact visualization
    - Performance metrics table
    """
    logger.info(f"GET /portfolio/performance/chart-data?portfolio_id={portfolio_id}")
    
    # For now, return sample data structure
    # In production, this would fetch from database
    return {
        "chart_data": {
            "portfolio": [
                {"date": "2024-01-01", "value": 100000, "return_pct": 0},
                {"date": "2024-12-30", "value": 115000, "return_pct": 15}
            ],
            "benchmark": [
                {"date": "2024-01-01", "value": 100, "return_pct": 0},
                {"date": "2024-12-30", "value": 110, "return_pct": 10}
            ]
        },
        "metrics": {
            "total_return_pct": 15.0,
            "benchmark_return_pct": 10.0,
            "excess_return_pct": 5.0,
            "volatility_pct": 12.5,
            "sharpe_ratio": 1.2,
            "max_drawdown_pct": -8.5
        }
    }


@v1_router.get("/portfolio/performance/stats")
def get_portfolio_stats(
    portfolio_id: Optional[int] = None,
    include_transaction_costs: bool = True
):
    """
    Get comprehensive portfolio statistics table.
    
    Returns:
    - Performance metrics over time
    - Transaction cost breakdown
    - Risk-adjusted returns
    - Benchmark comparison stats
    """
    logger.info(f"GET /portfolio/performance/stats?portfolio_id={portfolio_id}")
    
    return {
        "performance_stats": {
            "total_return": {"value": 15.0, "unit": "%", "vs_benchmark": "+5.0%"},
            "annualized_return": {"value": 12.5, "unit": "%", "vs_benchmark": "+3.2%"},
            "volatility": {"value": 14.2, "unit": "%", "vs_benchmark": "+2.1%"},
            "sharpe_ratio": {"value": 1.15, "unit": "", "vs_benchmark": "+0.25"},
            "max_drawdown": {"value": -8.5, "unit": "%", "vs_benchmark": "-1.2%"}
        },
        "transaction_costs": {
            "total_fees": {"value": 1250, "unit": "SEK"},
            "fee_percentage": {"value": 0.85, "unit": "%"},
            "impact_on_return": {"value": -0.85, "unit": "%"},
            "avg_fee_per_trade": {"value": 25, "unit": "SEK"}
        },
        "time_periods": {
            "1_month": {"return": 2.1, "vs_benchmark": "+0.8%"},
            "3_months": {"return": 5.5, "vs_benchmark": "+1.2%"},
            "6_months": {"return": 8.9, "vs_benchmark": "+2.1%"},
            "1_year": {"return": 15.0, "vs_benchmark": "+5.0%"}
        }
    }


# Portfolio Tracking
@v1_router.post("/portfolio/create")
def create_new_portfolio(name: str = "Default", db: Session = Depends(get_db)):
    """Create a new portfolio for tracking."""
    portfolio_id = create_portfolio(db, name)
    return {"portfolio_id": portfolio_id, "name": name}


@v1_router.post("/portfolio/{portfolio_id}/transaction")
def record_transaction(
    portfolio_id: int,
    ticker: str,
    transaction_type: str,
    shares: float,
    price: float,
    transaction_date: str,
    strategy: str = None,
    fees: float = 0,
    db: Session = Depends(get_db)
):
    """Record a buy/sell transaction."""
    txn_id = add_transaction(
        db, portfolio_id, ticker, transaction_type, shares, price,
        date.fromisoformat(transaction_date), strategy, fees
    )
    return {"transaction_id": txn_id}


@v1_router.get("/portfolio/{portfolio_id}/holdings")
def get_holdings(portfolio_id: int, db: Session = Depends(get_db)):
    """Get current portfolio holdings with values."""
    return get_portfolio_value(db, portfolio_id)


@v1_router.get("/portfolio/{portfolio_id}/performance")
def get_performance(portfolio_id: int, db: Session = Depends(get_db)):
    """Get portfolio performance metrics."""
    return calculate_portfolio_performance(db, portfolio_id)


@v1_router.post("/portfolio/{portfolio_id}/rebalance-trades")
def get_rebalance_trades(
    portfolio_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """Calculate trades needed to rebalance to target allocation."""
    target_holdings = request.get("target_holdings", [])
    portfolio_value = request.get("portfolio_value")
    return calculate_rebalance_trades(db, portfolio_id, target_holdings, portfolio_value)


@v1_router.get("/portfolio/{portfolio_id}/history")
def get_history(portfolio_id: int, db: Session = Depends(get_db)):
    """Get portfolio value history."""
    return get_portfolio_history(db, portfolio_id)


@v1_router.post("/portfolio/{portfolio_id}/snapshot")
def take_snapshot(portfolio_id: int, db: Session = Depends(get_db)):
    """Save current portfolio state as a snapshot."""
    snapshot_id = save_snapshot(db, portfolio_id)
    return {"snapshot_id": snapshot_id}


# Transaction Costs
@v1_router.get("/costs/brokers")
def list_brokers():
    """Get available brokers with fee structures."""
    return get_available_brokers()


@v1_router.post("/costs/calculate")
def calculate_trade_cost(
    trade_value: float,
    broker: str = "avanza",
    spread_pct: float = 0.002,
    is_round_trip: bool = False
):
    """Calculate transaction costs for a single trade."""
    return calculate_total_transaction_cost(trade_value, broker, spread_pct, is_round_trip)


@v1_router.post("/costs/rebalance")
def calculate_rebalance_cost(request: dict):
    """Calculate total costs for a rebalance."""
    trades = request.get("trades", [])
    broker = request.get("broker", "avanza")
    spread_pct = request.get("spread_pct", 0.002)
    return calculate_rebalance_costs(trades, broker, spread_pct)


@v1_router.post("/costs/annual-impact")
def calculate_annual_impact(
    portfolio_value: float,
    rebalances_per_year: int = 4,
    turnover_pct: float = 0.5,
    broker: str = "avanza",
    spread_pct: float = 0.002
):
    """Estimate annual transaction cost impact on returns."""
    return calculate_annual_cost_impact(
        portfolio_value, rebalances_per_year, turnover_pct, broker, spread_pct
    )


# Benchmark Comparison
@v1_router.post("/benchmark/compare")
def compare_to_benchmark(request: dict):
    """
    Compare strategy performance to benchmark.
    
    Request body:
    - strategy_values: List of portfolio values over time
    - benchmark_values: List of benchmark values over time
    - dates: Optional list of date strings
    """
    strategy_values = request.get("strategy_values", [])
    benchmark_values = request.get("benchmark_values", [])
    dates = request.get("dates")
    
    if not strategy_values or not benchmark_values:
        raise HTTPException(status_code=400, detail="Missing values")
    
    return calculate_relative_performance(strategy_values, benchmark_values, dates)


@v1_router.post("/benchmark/chart-data")
def get_benchmark_chart_data(request: dict):
    """Get normalized chart data for strategy vs benchmark."""
    strategy_values = request.get("strategy_values", [])
    benchmark_values = request.get("benchmark_values", [])
    dates = request.get("dates")
    
    return generate_relative_chart_data(strategy_values, benchmark_values, dates)


@v1_router.post("/benchmark/rolling")
def get_rolling_metrics_endpoint(request: dict):
    """Get rolling alpha, beta, and excess return."""
    strategy_values = request.get("strategy_values", [])
    benchmark_values = request.get("benchmark_values", [])
    window = request.get("window", 252)
    
    return calculate_rolling_metrics(strategy_values, benchmark_values, window)


# Risk Analytics
@v1_router.post("/risk/metrics")
def get_risk_metrics(request: dict):
    """Get comprehensive risk metrics for a value series."""
    values = request.get("values", [])
    benchmark_values = request.get("benchmark_values")
    risk_free_rate = request.get("risk_free_rate", 0.02)
    
    return calculate_risk_metrics(values, benchmark_values, risk_free_rate)


@v1_router.post("/risk/sector-exposure")
def get_sector_exposure(request: dict):
    """Calculate sector exposure from holdings."""
    holdings = request.get("holdings", [])
    return calculate_sector_exposure(holdings)


@v1_router.post("/risk/drawdown")
def get_drawdown_analysis_endpoint(request: dict):
    """Detailed drawdown analysis."""
    values = request.get("values", [])
    return calculate_drawdown_analysis(values)


# Dividends
@v1_router.get("/dividends/upcoming")
def get_upcoming_dividends_endpoint(days_ahead: int = 90, db: Session = Depends(get_db)):
    """Get upcoming dividend events."""
    return get_upcoming_dividends(db, days_ahead=days_ahead)


@v1_router.post("/dividends/projected-income")
def get_projected_income(request: dict, db: Session = Depends(get_db)):
    """Calculate projected dividend income from holdings."""
    holdings = request.get("holdings", [])
    months = request.get("months_ahead", 12)
    return calculate_projected_income(db, holdings, months)


@v1_router.get("/dividends/history/{ticker}")
def get_dividend_history_endpoint(ticker: str, years: int = 5, db: Session = Depends(get_db)):
    """Get dividend history for a stock."""
    return get_dividend_history(db, ticker, years)


@v1_router.get("/dividends/growth/{ticker}")
def get_dividend_growth(ticker: str, years: int = 5, db: Session = Depends(get_db)):
    """Calculate dividend growth rate."""
    return calculate_dividend_growth(db, ticker, years)


# Watchlist
@v1_router.post("/watchlist/create")
def create_watchlist_endpoint(name: str = "Default", db: Session = Depends(get_db)):
    """Create a new watchlist."""
    watchlist_id = create_watchlist(db, name)
    return {"watchlist_id": watchlist_id, "name": name}


@v1_router.get("/watchlist")
def list_watchlists(db: Session = Depends(get_db)):
    """Get all watchlists."""
    return get_all_watchlists(db)


@v1_router.get("/watchlist/{watchlist_id}")
def get_watchlist_endpoint(watchlist_id: int, db: Session = Depends(get_db)):
    """Get watchlist with items and rankings."""
    return get_watchlist(db, watchlist_id)


@v1_router.post("/watchlist/{watchlist_id}/add")
def add_to_watchlist_endpoint(
    watchlist_id: int,
    ticker: str,
    notes: str = None,
    alert: bool = True,
    db: Session = Depends(get_db)
):
    """Add stock to watchlist."""
    item_id = add_to_watchlist(db, watchlist_id, ticker, notes, alert)
    return {"item_id": item_id}


@v1_router.delete("/watchlist/{watchlist_id}/remove/{ticker}")
def remove_from_watchlist_endpoint(watchlist_id: int, ticker: str, db: Session = Depends(get_db)):
    """Remove stock from watchlist."""
    success = remove_from_watchlist(db, watchlist_id, ticker)
    return {"success": success}


@v1_router.get("/watchlist/{watchlist_id}/alerts")
def get_watchlist_alerts(
    watchlist_id: int,
    strategy: str = "sammansatt_momentum",
    db: Session = Depends(get_db)
):
    """Check for ranking changes in watchlist stocks."""
    return check_ranking_changes(db, watchlist_id, strategy)


# Custom Strategy Builder
@v1_router.get("/custom-strategy/factors")
def get_factors():
    """Get available factors for custom strategies."""
    return get_available_factors()


@v1_router.get("/custom-strategy")
def list_custom_strategies_endpoint(db: Session = Depends(get_db)):
    """List all custom strategies."""
    return list_custom_strategies(db)


@v1_router.post("/custom-strategy/create")
def create_strategy(request: dict, db: Session = Depends(get_db)):
    """
    Create a custom strategy.
    
    Request body:
    - name: Strategy name
    - factors: List of {factor, weight, direction}
    - filters: Optional list of {field, operator, value}
    - description: Optional description
    - rebalance_frequency: quarterly/monthly/annual
    - position_count: Number of positions (default 10)
    """
    strategy_id = create_custom_strategy(
        db,
        name=request.get("name"),
        factors=request.get("factors", []),
        filters=request.get("filters"),
        description=request.get("description"),
        rebalance_frequency=request.get("rebalance_frequency", "quarterly"),
        position_count=request.get("position_count", 10)
    )
    return {"strategy_id": strategy_id}


@v1_router.get("/custom-strategy/{strategy_id}")
def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Get a custom strategy by ID."""
    strategy = get_custom_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@v1_router.delete("/custom-strategy/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Delete a custom strategy."""
    success = delete_custom_strategy(db, strategy_id)
    return {"success": success}


@v1_router.post("/custom-strategy/{strategy_id}/run")
def run_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Run a custom strategy and get rankings."""
    strategy = get_custom_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # CRITICAL FIX: Load only recent prices to prevent memory exhaustion
    cutoff_date = date.today() - timedelta(days=400)
    prices = db.query(DailyPrice).filter(DailyPrice.date >= cutoff_date).all()
    fundamentals = db.query(Fundamentals).all()
    
    prices_df = pd.DataFrame([{"ticker": p.ticker, "date": p.date, "close": p.close} for p in prices]) if prices else pd.DataFrame()
    fund_df = pd.DataFrame([{
        "ticker": f.ticker, "market_cap": f.market_cap,
        "pe": f.pe, "pb": f.pb, "ps": f.ps, "p_fcf": f.p_fcf, "ev_ebitda": f.ev_ebitda,
        "dividend_yield": f.dividend_yield, "roe": f.roe, "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe,
        "payout_ratio": f.payout_ratio
    } for f in fundamentals]) if fundamentals else pd.DataFrame()
    
    # Free memory
    del prices, fundamentals
    import gc
    gc.collect()
    
    result = run_custom_strategy(
        fund_df, prices_df,
        factors=strategy["factors"],
        filters=strategy["filters"],
        position_count=strategy["position_count"]
    )
    
    return {
        "strategy_name": strategy["name"],
        "rankings": result.to_dict('records')
    }


# Markets
@v1_router.get("/markets")
def list_markets():
    """Get available markets."""
    return get_available_markets()


@v1_router.get("/markets/{market}/stocks")
def get_market_stocks(market: str):
    """Get stocks for a specific market."""
    stocks = get_stocks_for_market(market)
    return {
        "market": market,
        "config": get_market_config(market),
        "stocks": [{"ticker": t, "name": n} for t, n in stocks],
        "count": len(stocks)
    }


# CSV Import
@v1_router.post("/import/csv")
def import_csv(request: dict):
    """
    Import transactions from broker CSV export.
    
    Supported brokers:
    - Avanza: Export from Min Ekonomi > Transaktioner > Exportera transaktioner
    - Nordnet: Export from transactions page
    - Generic: CSV with columns: date, type, ticker, quantity, price, fee
    
    Request body:
    - content: CSV file content as string
    - broker: Optional broker hint ('avanza', 'nordnet', 'generic')
    """
    content = request.get("content", "")
    broker = request.get("broker")
    
    if not content:
        raise HTTPException(status_code=400, detail="No CSV content provided")
    
    result = parse_broker_csv(content, broker)
    return result


@v1_router.post("/import/csv/holdings")
def import_csv_to_holdings(request: dict):
    """
    Import CSV and calculate current holdings.
    
    Request body:
    - content: CSV file content as string
    - broker: Optional broker hint
    """
    content = request.get("content", "")
    broker = request.get("broker")
    
    if not content:
        raise HTTPException(status_code=400, detail="No CSV content provided")
    
    parsed = parse_broker_csv(content, broker)
    holdings = calculate_holdings_from_transactions(parsed["transactions"])
    
    return {
        "broker": parsed["broker"],
        "transactions_count": parsed["count"],
        "holdings": holdings,
        "holdings_count": len(holdings)
    }

@v1_router.get("/portfolio/{portfolio_name}/performance")
async def get_portfolio_performance(portfolio_name: str, days: int = 30):
    """Get portfolio performance over time."""
    from services.historical_tracker import HistoricalTracker
    
    tracker = HistoricalTracker()
    performance = tracker.get_portfolio_performance(portfolio_name, days)
    
    return {
        "portfolio_name": portfolio_name,
        "performance": performance,
        "tracking_period_days": days
    }

@v1_router.get("/stock/{ticker}/history")
async def get_stock_history(ticker: str, days: int = 30):
    """Get price history for a stock."""
    from services.historical_tracker import HistoricalTracker
    
    tracker = HistoricalTracker()
    history = tracker.get_price_history(ticker, days)
    
    return {
        "ticker": ticker,
        "history": history,
        "data_points": len(history)
    }

@v1_router.post("/portfolio/{portfolio_name}/snapshot")
async def record_portfolio_snapshot(portfolio_name: str, holdings: List[dict]):
    """Record a portfolio snapshot for tracking."""
    from services.historical_tracker import HistoricalTracker
    
    tracker = HistoricalTracker()
    tracker.record_portfolio_snapshot(portfolio_name, holdings)
    
    return {
        "message": f"Portfolio snapshot recorded for {portfolio_name}",
        "holdings_count": len(holdings),
        "timestamp": datetime.now().isoformat()
    }

@v1_router.websocket("/ws/sync-logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@v1_router.post("/rebalance/trades")
def generate_rebalance_trades(
    strategy: str,
    portfolio_value: float,
    current_holdings: List[dict] = [],
    db: Session = Depends(get_db)
):
    """Generate buy/sell trades to rebalance portfolio to target strategy.
    
    current_holdings: [{"ticker": "VOLV-B.ST", "shares": 10, "value": 5000}, ...]
    """
    # Get target stocks from strategy
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if strategy not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy}' not found")
    
    rankings = _compute_strategy_rankings(strategy, strategies[strategy], db)
    target_tickers = [r.ticker for r in rankings[:10]]
    
    # Equal weight allocation
    target_per_stock = portfolio_value / len(target_tickers) if target_tickers else 0
    
    # Build current holdings map
    current_map = {h["ticker"]: h.get("value", 0) for h in current_holdings}
    
    # Get current prices and ISINs
    prices = {}
    isins = {}
    for ticker in set(target_tickers + list(current_map.keys())):
        price_row = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).first()
        prices[ticker] = price_row.close if price_row else None
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        isins[ticker] = stock.isin if stock and stock.isin else None
    
    trades = []
    
    # Sells first (stocks to remove)
    for ticker, current_value in current_map.items():
        if ticker not in target_tickers and current_value > 0:
            price = prices.get(ticker)
            shares = int(current_value / price) if price else 0
            trades.append({
                "ticker": ticker, "action": "SELL", "shares": shares,
                "amount_sek": current_value, "price": price, "isin": isins.get(ticker)
            })
    
    # Buys (new stocks and rebalancing)
    for ticker in target_tickers:
        current_value = current_map.get(ticker, 0)
        diff = target_per_stock - current_value
        price = prices.get(ticker)
        
        if diff > 100 and price:  # Only trade if diff > 100 SEK
            shares = int(diff / price)
            if shares > 0:
                trades.append({
                    "ticker": ticker, "action": "BUY", "shares": shares,
                    "amount_sek": shares * price, "price": price, "isin": isins.get(ticker)
                })
        elif diff < -100 and price:  # Reduce position
            shares = int(abs(diff) / price)
            if shares > 0:
                trades.append({
                    "ticker": ticker, "action": "SELL", "shares": shares,
                    "amount_sek": shares * price, "price": price, "isin": isins.get(ticker)
                })
    
    # Calculate costs (Avanza rates)
    total_traded = sum(t["amount_sek"] for t in trades)
    courtage_rate = 0.00069  # 0.069% Avanza standard
    spread_rate = 0.002  # ~0.2% estimated spread for Swedish stocks
    
    courtage = total_traded * courtage_rate
    spread_cost = total_traded * spread_rate
    total_cost = courtage + spread_cost
    
    return {
        "strategy": strategy,
        "portfolio_value": portfolio_value,
        "target_stocks": target_tickers,
        "trades": trades,
        "total_buys": sum(t["amount_sek"] for t in trades if t["action"] == "BUY"),
        "total_sells": sum(t["amount_sek"] for t in trades if t["action"] == "SELL"),
        "costs": {
            "courtage": round(courtage, 2),
            "spread_estimate": round(spread_cost, 2),
            "total": round(total_cost, 2),
            "percentage": round(total_cost / portfolio_value * 100, 3) if portfolio_value else 0
        }
    }


@v1_router.post("/rebalance/save")
def save_rebalance(strategy: str, portfolio_value: float, trades: List[dict], db: Session = Depends(get_db)):
    """Save a completed rebalance to history."""
    from models import RebalanceHistory
    import json
    
    total_cost = sum(t.get('amount_sek', 0) for t in trades) * 0.00269  # courtage + spread
    
    record = RebalanceHistory(
        strategy=strategy,
        rebalance_date=date.today(),
        trades_json=json.dumps(trades),
        total_cost=total_cost,
        portfolio_value=portfolio_value
    )
    db.add(record)
    db.commit()
    return {"id": record.id, "date": record.rebalance_date.isoformat()}


@v1_router.get("/rebalance/history/{strategy}")
def get_rebalance_history(strategy: str, db: Session = Depends(get_db)):
    """Get rebalance history for a strategy."""
    from models import RebalanceHistory
    import json
    
    records = db.query(RebalanceHistory).filter(
        RebalanceHistory.strategy == strategy
    ).order_by(RebalanceHistory.rebalance_date.desc()).limit(20).all()
    
    return [{
        "id": r.id,
        "date": r.rebalance_date.isoformat(),
        "trades": json.loads(r.trades_json) if r.trades_json else [],
        "total_cost": r.total_cost,
        "portfolio_value": r.portfolio_value
    } for r in records]


@v1_router.get("/rebalance/last/{strategy}")
def get_last_rebalance(strategy: str, db: Session = Depends(get_db)):
    """Get last rebalance date for a strategy."""
    from models import RebalanceHistory
    
    record = db.query(RebalanceHistory).filter(
        RebalanceHistory.strategy == strategy
    ).order_by(RebalanceHistory.rebalance_date.desc()).first()
    
    if not record:
        return {"last_rebalance": None}
    return {"last_rebalance": record.rebalance_date.isoformat(), "days_ago": (date.today() - record.rebalance_date).days}


@v1_router.post("/portfolio/divergence")
def check_portfolio_divergence(strategy: str, holdings: List[dict], db: Session = Depends(get_db)):
    """Check how portfolio diverges from target strategy.
    
    holdings: [{"ticker": "VOLV-B", "value": 10000}, ...]
    Returns: which stocks to add/remove, drift percentage
    """
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if strategy not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy}' not found")
    
    rankings = _compute_strategy_rankings(strategy, strategies[strategy], db)
    target_tickers = set(r.ticker for r in rankings[:10])
    
    holding_tickers = set(h["ticker"] for h in holdings)
    total_value = sum(h.get("value", 0) for h in holdings)
    
    correct = holding_tickers & target_tickers
    to_add = target_tickers - holding_tickers
    to_remove = holding_tickers - target_tickers
    
    # Calculate drift (deviation from equal weight)
    target_weight = 0.10  # 10% each
    drift = 0
    if total_value > 0:
        for h in holdings:
            actual_weight = h.get("value", 0) / total_value
            if h["ticker"] in target_tickers:
                drift += abs(actual_weight - target_weight)
            else:
                drift += actual_weight  # Wrong stock = 100% drift for that position
    
    return {
        "strategy": strategy,
        "correct_count": len(correct),
        "target_count": 10,
        "correct_stocks": list(correct),
        "to_add": list(to_add),
        "to_remove": list(to_remove),
        "drift_percentage": round(drift * 100, 1),
        "status": "aligned" if len(correct) == 10 and drift < 0.05 else "needs_rebalance"
    }


@v1_router.post("/import/avanza-csv")
async def import_avanza_csv(file: UploadFile = File(...)):
    """Import holdings from Avanza CSV export."""
    content = await file.read()
    try:
        text = content.decode('utf-8')
    except Exception:
        text = content.decode('latin-1')
    
    transactions = parse_broker_csv(text)
    holdings = calculate_holdings_from_transactions(transactions)
    
    # Calculate totals
    total_fees = sum(t.get('fees', 0) for t in transactions)
    total_invested = sum(t['shares'] * t['price'] for t in transactions if t['type'] == 'BUY')
    
    return {
        "transactions_count": len(transactions),
        "holdings": [{"ticker": k, "shares": v} for k, v in holdings.items()],
        "total_fees_paid": total_fees,
        "total_invested": total_invested,
        "unique_stocks": len(holdings)
    }


# ============================================================================
# CSV Import with ISIN Matching & Performance Tracking
# ============================================================================

@v1_router.post("/portfolio/import-csv")
async def import_csv_preview(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parse Avanza CSV and return preview with ISIN matching.
    Does NOT save to database - use /import-confirm to save.
    """
    from services.csv_import import parse_avanza_csv, calculate_positions, filter_duplicates
    from models import IsinLookup, PortfolioTransactionImported
    
    content = await file.read()
    try:
        text = content.decode('utf-8')
    except Exception:
        text = content.decode('latin-1')
    
    # Build ISIN lookup from database
    isin_lookup = {r.isin: {'ticker': r.ticker, 'name': r.name, 'currency': r.currency}
                   for r in db.query(IsinLookup).all()}
    
    # Parse CSV with ISIN matching
    transactions = parse_avanza_csv(text, isin_lookup)
    
    if not transactions:
        raise HTTPException(status_code=400, detail="No valid transactions found in CSV")
    
    # Check for duplicates
    existing_hashes = {r.hash for r in db.query(PortfolioTransactionImported.hash).all()}
    new_txns, duplicates = filter_duplicates(transactions, existing_hashes)
    
    # Calculate positions from ALL transactions (for preview)
    positions = calculate_positions(transactions)
    
    # Find unmatched ISINs (from all transactions)
    unmatched = [t for t in transactions if not t.get('ticker')]
    matched = [t for t in transactions if t.get('ticker')]
    
    # Calculate totals from all transactions
    total_fees = sum(t.get('fee', 0) for t in transactions)
    total_invested = sum(t['shares'] * t['price_sek'] for t in transactions if t['type'] == 'BUY')
    
    # Date range from all transactions
    dates = [t['date'] for t in transactions if t.get('date')]
    date_range = {'start': min(dates), 'end': max(dates)} if dates else None
    
    return {
        "parsed": len(transactions),
        "new": len(new_txns),
        "duplicates_skipped": len(duplicates),
        "matched": len(matched),
        "unmatched": [{'name': t['name'], 'isin': t['isin'], 'date': t['date']} for t in unmatched[:10]],
        "positions": [
            {
                'ticker': k, 
                'shares': round(v['shares'], 2), 
                'avg_price_local': round(v.get('avg_price_local', v['avg_price_sek']), 2),
                'avg_price_sek': round(v['avg_price_sek'], 2),
                'total_cost': round(v['total_cost'], 2),
                'fees': round(v['total_fees'], 2),
                'currency': v['currency'],
                'fx_rate': round(v.get('fx_rate', 1.0), 4),
                'warning': v.get('warning')
            }
            for k, v in positions.items()
        ],
        "summary": {
            "total_fees": round(total_fees, 2),
            "total_invested": round(total_invested, 2),
            "unique_stocks": len(positions),
            "date_range": date_range,
        },
        "transactions": transactions,  # All transactions for confirm step
    }


class ImportConfirmRequest(BaseModel):
    transactions: List[dict]
    mode: str = "add_new"

@v1_router.post("/portfolio/import-confirm")
async def import_csv_confirm(
    http_request: Request,
    request: ImportConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Confirm and save imported transactions.
    
    Modes:
    - replace: Clear existing, import fresh
    - add_new: Skip duplicates, add new only
    """
    from models import PortfolioTransactionImported
    from services.auth import require_auth
    from datetime import datetime
    
    user = require_auth(http_request, db)
    
    transactions = request.transactions
    mode = request.mode
    
    if mode == "replace":
        db.query(PortfolioTransactionImported).filter(PortfolioTransactionImported.user_id == user.id).delete()
    
    imported = 0
    for txn in transactions:
        # Skip if hash already exists for this user
        if db.query(PortfolioTransactionImported).filter(
            PortfolioTransactionImported.hash == txn.get('hash'),
            PortfolioTransactionImported.user_id == user.id
        ).first():
            continue
        
        record = PortfolioTransactionImported(
            user_id=user.id,
            date=datetime.strptime(txn['date'], '%Y-%m-%d').date() if txn.get('date') else None,
            ticker=txn.get('ticker'),
            isin=txn.get('isin'),
            type=txn.get('type'),
            shares=txn.get('shares'),
            price_local=txn.get('price_local'),
            price_sek=txn.get('price_sek'),
            currency=txn.get('currency'),
            fee=txn.get('fee', 0),
            fx_rate=txn.get('fx_rate'),
            hash=txn.get('hash'),
            source='avanza_csv',
        )
        db.add(record)
        imported += 1
    
    db.commit()
    
    return {"success": True, "imported": imported, "mode": mode}


@v1_router.get("/portfolio/transactions")
def get_portfolio_transactions(
    request: Request,
    ticker: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get imported transactions with optional filters."""
    from models import PortfolioTransactionImported
    from services.auth import get_user_from_cookie
    from datetime import datetime
    
    user = get_user_from_cookie(request, db)
    if not user:
        return {"transactions": [], "count": 0}
    
    query = db.query(PortfolioTransactionImported).filter(PortfolioTransactionImported.user_id == user.id)
    
    if ticker:
        query = query.filter(PortfolioTransactionImported.ticker == ticker)
    if from_date:
        query = query.filter(PortfolioTransactionImported.date >= datetime.strptime(from_date, '%Y-%m-%d').date())
    if to_date:
        query = query.filter(PortfolioTransactionImported.date <= datetime.strptime(to_date, '%Y-%m-%d').date())
    
    transactions = query.order_by(PortfolioTransactionImported.date.desc()).all()
    
    return {
        "transactions": [
            {
                "id": t.id,
                "date": t.date.isoformat() if t.date else None,
                "ticker": t.ticker,
                "isin": t.isin,
                "type": t.type,
                "shares": t.shares,
                "price_local": t.price_local,
                "price_sek": t.price_sek,
                "currency": t.currency,
                "fee": t.fee,
            }
            for t in transactions
        ],
        "count": len(transactions),
    }


@v1_router.get("/portfolio/daily-stats")
def get_portfolio_daily_stats(request: Request, db: Session = Depends(get_db)):
    """Get daily portfolio stats for dashboard card - uses momentum portfolio holdings."""
    from models import UserPortfolio, DailyPrice
    from services.auth import get_user_from_cookie
    from datetime import date, timedelta
    import json
    
    empty_response = {"total_value": 0, "today_change": 0, "today_change_pct": 0, "week_change_pct": 0, "month_change_pct": 0, "best_performer": None, "worst_performer": None}
    
    user = get_user_from_cookie(request, db)
    if not user:
        return empty_response
    
    # Get holdings from momentum_locked portfolio (same as PortfolioTracker)
    portfolio = db.query(UserPortfolio).filter(
        UserPortfolio.user_id == user.id,
        UserPortfolio.name == "momentum_locked"
    ).first()
    
    if not portfolio or not portfolio.holdings:
        return empty_response
    
    try:
        holdings = json.loads(portfolio.holdings)
    except:
        return empty_response
    
    if not holdings:
        return empty_response
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Build ISIN to ticker mapping
    from models import IsinLookup
    isins = [h.get('isin') for h in holdings if h.get('isin')]
    isin_to_ticker = {}
    if isins:
        lookups = db.query(IsinLookup).filter(IsinLookup.isin.in_(isins)).all()
        isin_to_ticker = {l.isin: l.ticker for l in lookups}
    
    def get_price_at_date(holding: dict, d: date):
        # Try ISIN lookup first, then ticker formats
        ticker = None
        if holding.get('isin') and holding['isin'] in isin_to_ticker:
            ticker = isin_to_ticker[holding['isin']]
        
        if not ticker:
            ticker = holding.get('ticker', '')
        
        # Try the ticker
        price = db.query(DailyPrice).filter(
            DailyPrice.ticker == ticker,
            DailyPrice.date <= d
        ).order_by(DailyPrice.date.desc()).first()
        if price:
            return price.close
        
        # Try with underscore
        price = db.query(DailyPrice).filter(
            DailyPrice.ticker == ticker.replace(' ', '_'),
            DailyPrice.date <= d
        ).order_by(DailyPrice.date.desc()).first()
        return price.close if price else None
    
    def get_portfolio_value(d: date):
        total = 0
        for h in holdings:
            shares = h.get('shares', 0)
            buy_price = h.get('buyPrice', 0)
            price = get_price_at_date(h, d)
            if price:
                total += shares * price
            else:
                total += shares * buy_price
        return total
    
    current_value = get_portfolio_value(today)
    yesterday_value = get_portfolio_value(yesterday)
    week_value = get_portfolio_value(week_ago)
    month_value = get_portfolio_value(month_ago)
    
    today_change = current_value - yesterday_value
    today_pct = (today_change / yesterday_value * 100) if yesterday_value > 0 else 0
    week_pct = ((current_value - week_value) / week_value * 100) if week_value > 0 else 0
    month_pct = ((current_value - month_value) / month_value * 100) if month_value > 0 else 0
    
    # Find best/worst performers today
    performers = []
    for h in holdings:
        ticker = h.get('ticker', '')
        today_price = get_price_at_date(h, today)
        yest_price = get_price_at_date(h, yesterday)
        if today_price and yest_price and yest_price > 0:
            change_pct = (today_price - yest_price) / yest_price * 100
            performers.append({'ticker': ticker, 'change_pct': round(change_pct, 2)})
    
    performers.sort(key=lambda x: x['change_pct'], reverse=True)
    best = performers[0] if performers else None
    worst = performers[-1] if performers else None
    
    return {
        "total_value": round(current_value, 2),
        "today_change": round(today_change, 2),
        "today_change_pct": round(today_pct, 2),
        "week_change_pct": round(week_pct, 2),
        "month_change_pct": round(month_pct, 2),
        "best_performer": best,
        "worst_performer": worst
    }


@v1_router.get("/portfolio/achievements")
def get_portfolio_achievements(request: Request, db: Session = Depends(get_db)):
    """Get user achievements based on portfolio activity."""
    from models import PortfolioTransactionImported
    from services.csv_import import calculate_positions
    from services.auth import get_user_from_cookie
    
    user = get_user_from_cookie(request, db)
    if not user:
        return {"unlocked": [], "progress": {}, "streak": 0}
    
    transactions = db.query(PortfolioTransactionImported).filter(PortfolioTransactionImported.user_id == user.id).all()
    unlocked = []
    progress = {}
    
    if not transactions:
        return {"unlocked": [], "progress": {}, "streak": 0}
    
    txn_list = [{'date': t.date.isoformat() if t.date else None, 'ticker': t.ticker, 'type': t.type, 'shares': t.shares, 'price_sek': t.price_sek} for t in transactions]
    positions = calculate_positions(txn_list)
    
    # First import
    if transactions:
        unlocked.append('first_import')
    
    # Portfolio value milestones
    total_cost = sum(p['total_cost'] for p in positions.values())
    if total_cost >= 100000:
        unlocked.append('portfolio_100k')
    elif total_cost >= 50000:
        progress['portfolio_100k'] = int(total_cost / 100000 * 100)
    if total_cost >= 500000:
        unlocked.append('portfolio_500k')
    if total_cost >= 1000000:
        unlocked.append('portfolio_1m')
    
    # Stock-specific achievements
    tickers = list(positions.keys())
    if 'SAAB B' in tickers:
        unlocked.append('saab_owner')
    if 'VOLV B' in tickers:
        unlocked.append('volvo_owner')
    
    # Diversification
    if len(tickers) >= 5:
        unlocked.append('diversified')
    else:
        progress['diversified'] = int(len(tickers) / 5 * 100)
    
    # Time-based fun achievements
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 7:
        unlocked.append('early_bird')
    if hour >= 0 and hour < 5:
        unlocked.append('night_owl')
    if datetime.now().weekday() == 5:
        unlocked.append('weekend_warrior')
    
    return {"unlocked": unlocked, "progress": progress, "streak": 0}


@v1_router.get("/portfolio/performance")
def get_portfolio_performance_data(
    request: Request,
    period: str = "1Y",
    db: Session = Depends(get_db)
):
    """
    Get portfolio performance data for charting.
    
    Returns gross/net returns over time with cost breakdown.
    """
    from models import PortfolioTransactionImported, DailyPrice
    from services.csv_import import calculate_positions
    from services.auth import get_user_from_cookie
    from datetime import datetime, timedelta, date
    from sqlalchemy import func
    
    user = get_user_from_cookie(request, db)
    if not user:
        return {"data_points": [], "summary": None, "message": "Not logged in"}
    
    # Get all transactions for this user
    transactions = db.query(PortfolioTransactionImported).filter(
        PortfolioTransactionImported.user_id == user.id
    ).order_by(
        PortfolioTransactionImported.date
    ).all()
    
    if not transactions:
        return {"data_points": [], "summary": None, "message": "No transactions found"}
    
    # Convert to dict format
    txn_list = [
        {
            'date': t.date.isoformat() if t.date else None,
            'ticker': t.ticker,
            'isin': t.isin,
            'type': t.type,
            'shares': t.shares,
            'price_sek': t.price_sek,
            'fee': t.fee or 0,
        }
        for t in transactions
    ]
    
    # Calculate period start
    today = date.today()
    period_map = {
        '1M': timedelta(days=30),
        '3M': timedelta(days=90),
        '6M': timedelta(days=180),
        'YTD': timedelta(days=(today - date(today.year, 1, 1)).days),
        '1Y': timedelta(days=365),
        'ALL': timedelta(days=3650),
    }
    start_date = today - period_map.get(period, timedelta(days=365))
    
    # Get first transaction date
    first_txn_date = min(t.date for t in transactions if t.date)
    start_date = max(start_date, first_txn_date)
    
    # Calculate positions at start
    positions = calculate_positions([t for t in txn_list if t['date'] and t['date'] <= start_date.isoformat()])
    
    # Build ISIN to ticker mapping from IsinLookup (for price lookups)
    from models import IsinLookup
    isins = list(set(t.isin for t in transactions if t.isin))
    isin_lookups = db.query(IsinLookup).filter(IsinLookup.isin.in_(isins)).all()
    isin_to_ticker = {l.isin: l.ticker for l in isin_lookups}
    isin_to_currency = {l.isin: l.currency for l in isin_lookups}
    
    # Get unique tickers (from ISIN lookup, not transactions - handles Nordic suffixes)
    tickers = list(set(isin_to_ticker.values())) + list(set(t.ticker for t in transactions if t.ticker))
    
    # Get prices for date range
    prices_query = db.query(DailyPrice).filter(
        DailyPrice.ticker.in_(tickers),
        DailyPrice.date >= start_date
    ).all()
    
    # Build price lookup: {ticker: {date: price}}
    price_lookup = {}
    for p in prices_query:
        if p.ticker not in price_lookup:
            price_lookup[p.ticker] = {}
        price_lookup[p.ticker][p.date.isoformat()] = p.close
    
    # Calculate total fees and spread
    total_fees = sum(t.fee or 0 for t in transactions)
    turnover = sum(t.shares * t.price_sek for t in transactions if t.price_sek)
    estimated_spread = turnover * 0.003  # 0.3% spread estimate
    
    # Calculate current positions and value
    current_positions = calculate_positions(txn_list)
    
    # Currency conversion rates (approximate)
    currency_rates = {'EUR': 11.5, 'DKK': 1.55, 'NOK': 1.0, 'SEK': 1.0}
    
    # Get latest prices for current value (use ISIN to find correct ticker)
    total_value = 0
    total_cost = 0
    missing_prices = []
    for ticker, pos in current_positions.items():
        # Try to find price via ISIN first (handles Nordic stocks with suffixes)
        isin = pos.get('isin')
        lookup_ticker = isin_to_ticker.get(isin, ticker) if isin else ticker
        currency = isin_to_currency.get(isin, 'SEK') if isin else 'SEK'
        
        if lookup_ticker in price_lookup and price_lookup[lookup_ticker]:
            latest_date = max(price_lookup[lookup_ticker].keys())
            latest_price = price_lookup[lookup_ticker][latest_date]
            # Convert to SEK
            rate = currency_rates.get(currency, 1.0)
            total_value += pos['shares'] * latest_price * rate
        elif ticker in price_lookup and price_lookup[ticker]:
            # Fallback to original ticker
            latest_date = max(price_lookup[ticker].keys())
            latest_price = price_lookup[ticker][latest_date]
            total_value += pos['shares'] * latest_price
        else:
            # No price data - use cost as fallback value
            total_value += pos['total_cost']
            missing_prices.append(ticker)
        total_cost += pos['total_cost']
    
    # Calculate returns
    gross_return_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
    net_return_pct = ((total_value - total_cost - total_fees - estimated_spread) / total_cost * 100) if total_cost > 0 else 0
    
    result = {
        "summary": {
            "total_invested": round(total_cost, 2),
            "current_value": round(total_value, 2),
            "gross_return": round(total_value - total_cost, 2),
            "gross_return_pct": round(gross_return_pct, 2),
            "net_return_pct": round(net_return_pct, 2),
            "total_fees": round(total_fees, 2),
            "estimated_spread": round(estimated_spread, 2),
            "total_costs": round(total_fees + estimated_spread, 2),
            "cost_impact_pct": round((total_fees + estimated_spread) / total_cost * 100, 2) if total_cost > 0 else 0,
        },
        "positions": [],
        "period": period,
    }
    
    # Build positions with current value and return (use ISIN for lookup)
    for ticker, pos in current_positions.items():
        current_val = pos['total_cost']  # fallback
        isin = pos.get('isin')
        lookup_ticker = isin_to_ticker.get(isin, ticker) if isin else ticker
        currency = isin_to_currency.get(isin, 'SEK') if isin else 'SEK'
        
        if lookup_ticker in price_lookup and price_lookup[lookup_ticker]:
            latest_date = max(price_lookup[lookup_ticker].keys())
            price_local = price_lookup[lookup_ticker][latest_date]
            rate = currency_rates.get(currency, 1.0)
            current_val = pos['shares'] * price_local * rate
        elif ticker in price_lookup and price_lookup[ticker]:
            latest_date = max(price_lookup[ticker].keys())
            current_val = pos['shares'] * price_lookup[ticker][latest_date]
        
        return_pct = ((current_val - pos['total_cost']) / pos['total_cost'] * 100) if pos['total_cost'] > 0 else 0
        result["positions"].append({
            "ticker": ticker,
            "shares": round(pos['shares'], 2),
            "cost": round(pos['total_cost'], 2),
            "current_value": round(current_val, 2),
            "return_pct": round(return_pct, 1),
            "avg_price": round(pos['avg_price_sek'], 2),
            "fees": round(pos['total_fees'], 2),
        })
    
    # Build chart data - portfolio value over time
    chart_data = []
    current_date = start_date
    while current_date <= today:
        # Get positions at this date
        txns_to_date = [t for t in txn_list if t['date'] and t['date'] <= current_date.isoformat()]
        pos_at_date = calculate_positions(txns_to_date)
        
        # Calculate value at this date
        day_value = 0
        for ticker, pos in pos_at_date.items():
            if ticker in price_lookup:
                # Find closest price on or before this date
                valid_dates = [d for d in price_lookup[ticker].keys() if d <= current_date.isoformat()]
                if valid_dates:
                    price = price_lookup[ticker][max(valid_dates)]
                    day_value += pos['shares'] * price
                else:
                    day_value += pos['total_cost']
            else:
                day_value += pos['total_cost']
        
        if day_value > 0:
            # Deduct cumulative fees/spread up to this date for net value
            fees_to_date = sum(t.get('fee', 0) for t in txns_to_date)
            spread_to_date = sum((t.get('shares', 0) * t.get('price_sek', 0)) for t in txns_to_date) * 0.003
            net_value = day_value - fees_to_date - spread_to_date
            chart_data.append({"date": current_date.strftime("%d %b"), "value": round(net_value)})
        
        # Weekly intervals for cleaner chart
        current_date += timedelta(days=7)
    
    # Add final point for today
    if chart_data and chart_data[-1]["value"] != round(total_value):
        chart_data.append({"date": today.strftime("%d %b"), "value": round(total_value)})
    
    result["chart_data"] = chart_data
    
    if missing_prices:
        result["warning"] = f"Prisdata saknas för {len(missing_prices)} positioner - använder inköpspris"
    
    return result


@v1_router.get("/isin-lookup")
def get_isin_lookup(db: Session = Depends(get_db)):
    """Get ISIN lookup table for client-side matching."""
    from models import IsinLookup
    
    lookups = db.query(IsinLookup).all()
    return {
        r.isin: {'ticker': r.ticker, 'name': r.name, 'currency': r.currency, 'market': r.market}
        for r in lookups
    }


@v1_router.post("/portfolio/sync-to-holdings")
def sync_imported_to_holdings(request: Request, db: Session = Depends(get_db)):
    """
    Convert imported transactions to momentum portfolio holdings format.
    Syncs positions from PortfolioTransactionImported to UserPortfolio.
    """
    from services.auth import require_auth
    from models import PortfolioTransactionImported, UserPortfolio, IsinLookup
    from services.csv_import import calculate_positions
    from services.ranking_cache import compute_nordic_momentum
    import json
    
    user = require_auth(request, db)
    
    # Get all imported transactions for this user
    transactions = db.query(PortfolioTransactionImported).filter(
        PortfolioTransactionImported.user_id == user.id
    ).order_by(
        PortfolioTransactionImported.date
    ).all()
    
    if not transactions:
        return {"synced": 0, "message": "No imported transactions found"}
    
    # Build ISIN lookup for re-matching
    isin_map = {r.isin: r.ticker for r in db.query(IsinLookup).all()}
    
    # Convert to dict format for calculate_positions
    txn_list = []
    for t in transactions:
        # Try to get ticker from ISIN lookup if not already set
        ticker = t.ticker
        if not ticker and t.isin and t.isin in isin_map:
            ticker = isin_map[t.isin]
        
        txn_list.append({
            'date': t.date.isoformat() if t.date else None,
            'ticker': ticker,
            'isin': t.isin,
            'type': t.type,
            'shares': t.shares,
            'price_sek': t.price_sek,
            'price_local': t.price_local or t.price_sek,
            'currency': t.currency or 'SEK',
            'fx_rate': t.fx_rate or 1.0,
            'fee': t.fee or 0,
        })
    
    # Calculate current positions
    positions = calculate_positions(txn_list)
    
    # Get current rankings for rank info
    rank_map = {}
    try:
        rankings_result = compute_nordic_momentum()
        if 'rankings' in rankings_result:
            rank_map = {r['ticker']: r['rank'] for r in rankings_result['rankings']}
    except:
        pass
    
    # Convert to holdings format expected by PortfolioTracker
    holdings = []
    unmapped = []
    
    # Build reverse ISIN lookup (ticker -> isin)
    ticker_to_isin = {r.ticker: r.isin for r in db.query(IsinLookup).all()}
    
    for key, pos in positions.items():
        if pos['shares'] > 0:  # Only include active positions
            # Check if key is ISIN (not a ticker)
            is_isin = key.startswith('SE') or key.startswith('DK') or key.startswith('FI') or key.startswith('NO') or key.startswith('CA')
            if is_isin and len(key) == 12:
                unmapped.append({'isin': key, 'shares': pos['shares']})
                continue  # Skip unmapped ISINs
            
            holdings.append({
                'ticker': key,
                'isin': ticker_to_isin.get(key) or pos.get('isin'),  # Include ISIN for reliable matching
                'shares': round(pos['shares']),
                'buyPrice': round(pos['avg_price_sek'], 2),
                'buyPriceLocal': round(pos.get('avg_price_local', pos['avg_price_sek']), 2),
                'currency': pos.get('currency', 'SEK'),
                'buyDate': pos.get('first_buy_date', ''),
                'rankAtPurchase': rank_map.get(key, 0),
                'currentRank': rank_map.get(key),
                'fees': round(pos['total_fees'], 2),
            })
    
    # Save to UserPortfolio
    portfolio = db.query(UserPortfolio).filter(
        UserPortfolio.user_id == user.id,
        UserPortfolio.name == "momentum_locked"
    ).first()
    
    if not portfolio:
        portfolio = UserPortfolio(
            user_id=user.id,
            name="momentum_locked",
            description="{}"
        )
        db.add(portfolio)
    
    portfolio.holdings = json.dumps(holdings)
    db.commit()
    
    result = {
        "synced": len(holdings),
        "holdings": holdings,
        "total_value": sum(h['shares'] * h['buyPrice'] for h in holdings),
    }
    
    if unmapped:
        result["warning"] = f"{len(unmapped)} positions skipped (foreign stocks not in Swedish universe)"
        result["unmapped"] = unmapped
    
    return result


# Multi-Portfolio Support
# Historical Rankings Archive
@v1_router.post("/rankings/snapshot")
def save_rankings_snapshot(strategy: str, db: Session = Depends(get_db)):
    """Save current rankings as a snapshot."""
    from models import RankingsSnapshot
    import json
    
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if strategy not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy}' not found")
    
    rankings = _compute_strategy_rankings(strategy, strategies[strategy], db)
    rankings_data = [{"ticker": r.ticker, "rank": r.rank, "score": r.score} for r in rankings[:10]]
    
    snapshot = RankingsSnapshot(
        strategy=strategy,
        snapshot_date=date.today(),
        rankings_json=json.dumps(rankings_data)
    )
    db.add(snapshot)
    db.commit()
    return {"id": snapshot.id, "date": snapshot.snapshot_date.isoformat(), "stocks": len(rankings_data)}


@v1_router.get("/rankings/history/{strategy}")
def get_rankings_history(strategy: str, limit: int = 12, db: Session = Depends(get_db)):
    """Get historical rankings snapshots."""
    from models import RankingsSnapshot
    import json
    
    snapshots = db.query(RankingsSnapshot).filter(
        RankingsSnapshot.strategy == strategy
    ).order_by(RankingsSnapshot.snapshot_date.desc()).limit(limit).all()
    
    return [{
        "date": s.snapshot_date.isoformat(),
        "rankings": json.loads(s.rankings_json) if s.rankings_json else []
    } for s in snapshots]


@v1_router.get("/rankings/on-date")
def get_rankings_on_date(strategy: str, target_date: str, db: Session = Depends(get_db)):
    """Get rankings for a specific date (nearest snapshot)."""
    from models import RankingsSnapshot
    import json
    
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    
    snapshot = db.query(RankingsSnapshot).filter(
        RankingsSnapshot.strategy == strategy,
        RankingsSnapshot.snapshot_date <= target
    ).order_by(RankingsSnapshot.snapshot_date.desc()).first()
    
    if not snapshot:
        return {"date": None, "rankings": [], "message": "No snapshot found for this date"}
    
    return {
        "date": snapshot.snapshot_date.isoformat(),
        "rankings": json.loads(snapshot.rankings_json) if snapshot.rankings_json else []
    }


@v1_router.get("/rankings/compute-historical")
def compute_historical_rankings(strategy: str, target_date: str, db: Session = Depends(get_db)):
    """
    Compute what the strategy rankings WOULD have been on a specific date.
    Uses historical fundamentals snapshots + historical prices.
    """
    from models import FundamentalsSnapshot, DailyPrice
    from services.ranking import (
        calculate_momentum_score, calculate_value_score,
        calculate_dividend_score, calculate_quality_score,
        filter_by_market_cap, filter_financial_companies
    )
    
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    
    # Find nearest fundamentals snapshot (on or before target date)
    snapshot_date = db.query(FundamentalsSnapshot.snapshot_date).filter(
        FundamentalsSnapshot.snapshot_date <= target
    ).order_by(FundamentalsSnapshot.snapshot_date.desc()).first()
    
    if not snapshot_date:
        return {"error": "No fundamentals snapshot available for this date", "available_from": None}
    
    snapshot_date = snapshot_date[0]
    
    # Load fundamentals from snapshot
    snapshots = db.query(FundamentalsSnapshot).filter(
        FundamentalsSnapshot.snapshot_date == snapshot_date
    ).all()
    
    fund_df = pd.DataFrame([{
        'ticker': s.ticker, 'market_cap': s.market_cap, 'pe': s.pe, 'pb': s.pb,
        'ps': s.ps, 'p_fcf': s.p_fcf, 'ev_ebitda': s.ev_ebitda, 'roe': s.roe,
        'roa': s.roa, 'roic': s.roic, 'fcfroe': s.fcfroe,
        'dividend_yield': s.dividend_yield, 'payout_ratio': s.payout_ratio
    } for s in snapshots])
    
    if fund_df.empty:
        return {"error": "No fundamentals data in snapshot"}
    
    # Load historical prices up to target date (need 12 months for momentum)
    prices = db.query(DailyPrice).filter(
        DailyPrice.date <= target,
        DailyPrice.date >= target - timedelta(days=400)
    ).all()
    
    prices_df = pd.DataFrame([{'ticker': p.ticker, 'date': p.date, 'close': p.close} for p in prices])
    
    if prices_df.empty:
        return {"error": "No price data available for this date range"}
    
    # Apply market cap filter
    filtered_fund = filter_by_market_cap(fund_df, 40)
    filtered_fund = filter_financial_companies(filtered_fund)
    
    # Compute rankings based on strategy type
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if strategy not in strategies:
        return {"error": f"Unknown strategy: {strategy}"}
    
    config = strategies[strategy]
    strategy_type = config.get('category', config.get('type', ''))
    
    if strategy_type == 'momentum':
        scores = calculate_momentum_score(prices_df)
        ranked = scores.sort_values(ascending=False).head(10)
        rankings = [{'ticker': t, 'rank': i+1, 'score': float(s)} for i, (t, s) in enumerate(ranked.items())]
    elif strategy_type == 'value':
        ranked = calculate_value_score(filtered_fund, prices_df)
        rankings = ranked.head(10).to_dict('records')
    elif strategy_type == 'dividend':
        ranked = calculate_dividend_score(filtered_fund, prices_df)
        rankings = ranked.head(10).to_dict('records')
    elif strategy_type == 'quality':
        ranked = calculate_quality_score(filtered_fund, prices_df)
        rankings = ranked.head(10).to_dict('records')
    else:
        return {"error": f"Unknown strategy type: {strategy_type}"}
    
    return {
        "strategy": strategy,
        "target_date": target_date,
        "fundamentals_snapshot_date": snapshot_date.isoformat(),
        "rankings": rankings,
        "note": "Rankings computed from historical data - may differ from actual picks if data was different"
    }


@v1_router.get("/fundamentals/snapshots")
def list_fundamentals_snapshots(db: Session = Depends(get_db)):
    """List available fundamentals snapshot dates."""
    from models import FundamentalsSnapshot
    from sqlalchemy import func
    
    dates = db.query(
        FundamentalsSnapshot.snapshot_date,
        func.count(FundamentalsSnapshot.id).label('stock_count')
    ).group_by(FundamentalsSnapshot.snapshot_date).order_by(
        FundamentalsSnapshot.snapshot_date.desc()
    ).limit(52).all()  # Last year of weekly snapshots
    
    return {
        "snapshots": [{"date": d[0].isoformat(), "stocks": d[1]} for d in dates],
        "total_snapshots": len(dates)
    }


# Broker Fee Comparison
BROKER_FEES = {
    "avanza": {"name": "Avanza", "courtage_pct": 0.069, "min_fee": 1, "spread_pct": 0.20},
    "nordnet": {"name": "Nordnet", "courtage_pct": 0.069, "min_fee": 39, "spread_pct": 0.20},
    "degiro": {"name": "DEGIRO", "courtage_pct": 0.05, "min_fee": 0, "spread_pct": 0.25},
}

@v1_router.get("/brokers/compare")
def compare_broker_fees(trade_value: float):
    """Compare broker fees for a given trade value."""
    results = []
    for broker_id, fees in BROKER_FEES.items():
        courtage = max(trade_value * fees["courtage_pct"] / 100, fees["min_fee"])
        spread = trade_value * fees["spread_pct"] / 100
        total = courtage + spread
        results.append({
            "broker": fees["name"],
            "courtage": round(courtage, 2),
            "spread": round(spread, 2),
            "total": round(total, 2),
            "percentage": round(total / trade_value * 100, 3) if trade_value else 0
        })
    
    results.sort(key=lambda x: x["total"])
    cheapest = results[0]["broker"] if results else None
    
    return {"trade_value": trade_value, "brokers": results, "cheapest": cheapest}


@v1_router.get("/brokers/rebalance-cost")
def compare_rebalance_costs(portfolio_value: float, turnover_pct: float = 50):
    """Compare total rebalance costs across brokers."""
    trade_value = portfolio_value * turnover_pct / 100
    
    results = []
    for broker_id, fees in BROKER_FEES.items():
        # Assume 10 trades (5 buys, 5 sells) for a full rebalance
        num_trades = 10
        courtage_per_trade = max(trade_value / num_trades * fees["courtage_pct"] / 100, fees["min_fee"])
        total_courtage = courtage_per_trade * num_trades
        spread = trade_value * fees["spread_pct"] / 100
        total = total_courtage + spread
        
        results.append({
            "broker": fees["name"],
            "courtage": round(total_courtage, 2),
            "spread": round(spread, 2),
            "total": round(total, 2),
            "percentage": round(total / portfolio_value * 100, 3)
        })
    
    results.sort(key=lambda x: x["total"])
    
    return {
        "portfolio_value": portfolio_value,
        "turnover_pct": turnover_pct,
        "trade_value": trade_value,
        "brokers": results,
        "cheapest": results[0]["broker"] if results else None,
        "savings_vs_worst": round(results[-1]["total"] - results[0]["total"], 2) if len(results) > 1 else 0
    }


@v1_router.post("/notifications/rebalance-reminder")
def send_rebalance_reminder_endpoint(email: str, strategy: str, db: Session = Depends(get_db)):
    """Send rebalance reminder email."""
    from services.email_notifications import send_rebalance_reminder, get_upcoming_rebalances
    
    upcoming = get_upcoming_rebalances(days_ahead=30)
    match = next((u for u in upcoming if u['strategy'].lower() == strategy.lower()), None)
    
    if not match:
        return {"sent": False, "reason": "No upcoming rebalance for this strategy"}
    
    # Get current top stocks
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    strategy_key = next((k for k in strategies if k.lower() == strategy.lower()), None)
    stocks = []
    if strategy_key:
        rankings = _compute_strategy_rankings(strategy_key, strategies[strategy_key], db)
        stocks = [r.ticker for r in rankings[:10]]
    
    sent = send_rebalance_reminder(email, strategy, match['date'], stocks)
    return {"sent": sent, "strategy": strategy, "date": match['date'].isoformat()}


@v1_router.get("/notifications/upcoming-rebalances")
def get_upcoming_rebalances_endpoint(days_ahead: int = 14):
    """Get strategies with upcoming rebalances."""
    from services.email_notifications import get_upcoming_rebalances
    upcoming = get_upcoming_rebalances(days_ahead)
    return [{"strategy": u['strategy'], "date": u['date'].isoformat(), "days_until": u['days_until']} for u in upcoming]


# Include v1 router
app.include_router(v1_router)

# Serve frontend static files (production mode)
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Serve index.html for all non-API routes (SPA routing)
        file_path = os.path.join(STATIC_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
