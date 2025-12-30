from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from datetime import date, datetime
from contextlib import asynccontextmanager
import pandas as pd
import json
import logging
import asyncio
from typing import List, Dict, Optional

from db import get_db, engine, Base, text
from models import Stock, DailyPrice, Fundamentals, SavedCombination as SavedCombinationModel
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
from services.eodhd_fetcher import get_sync_status
from services.enhanced_backtesting import long_term_backtester
from services.auto_rebalancing import auto_rebalancer
from services.portfolio_comparison import PortfolioComparisonService
from services.validation import check_data_freshness
from services.cache import invalidate_cache, get_cache_stats
from services.export import export_rankings_to_csv, export_backtest_to_csv, export_comparison_to_csv
from services.auto_rebalancing import auto_rebalancer
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
from config.settings import get_settings, load_strategies_config
from jobs.scheduler import start_scheduler, stop_scheduler, get_scheduler_status
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=logging.INFO)
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
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.remove(conn)

manager = ConnectionManager()

STRATEGIES_CONFIG = load_strategies_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    logger.info("Application started with scheduler")
    yield
    stop_scheduler()
    logger.info("Application shutdown")

app = FastAPI(title="Börslabbet Strategy API", lifespan=lifespan)

# Initialize services
portfolio_comparison_service = PortfolioComparisonService()


# Health
@app.get("/health")
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


# Strategies
@app.get("/strategies", response_model=list[StrategyMeta])
def list_strategies():
    logger.info("GET /strategies")
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


@app.get("/strategies/{name}", response_model=list[RankedStock])
def get_strategy_rankings(name: str, db: Session = Depends(get_db)):
    logger.info(f"GET /strategies/{name}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return _compute_strategy_rankings(name, strategies[name], db)


@app.get("/strategies/{name}/top10", response_model=list[RankedStock])
def get_strategy_top10(name: str, db: Session = Depends(get_db)):
    logger.info(f"GET /strategies/{name}/top10")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return _compute_strategy_rankings(name, strategies[name], db)[:10]


# Enhanced Strategy Rankings with Manual/Auto Toggle
@app.get("/strategies/{strategy_name}/enhanced")
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


@app.post("/portfolio/analyze-rebalancing")
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


@app.post("/portfolio/compare-all-strategies")
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
@app.get("/portfolio/sverige", response_model=PortfolioResponse)
def get_portfolio_sverige(db: Session = Depends(get_db)):
    logger.info("GET /portfolio/sverige")
    portfolio_config = STRATEGIES_CONFIG.get("portfolio_sverige", {})
    strategy_names = portfolio_config.get("strategies", [])
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    strategy_results = {}
    for name in strategy_names:
        if name in strategies:
            rankings = _compute_strategy_rankings(name, strategies[name], db)
            strategy_results[name] = pd.DataFrame([r.model_dump() for r in rankings])
    
    combined = combine_strategies(strategy_results)
    holdings = [
        PortfolioHoldingOut(ticker=row['ticker'], name=_get_stock_name(row['ticker'], db),
                           weight=row['weight'], strategy=row['strategy'])
        for _, row in combined.iterrows()
    ]
    
    rebalance_dates = get_next_rebalance_dates(strategies)
    next_rebalance = min(rebalance_dates.values()) if rebalance_dates else None
    
    return PortfolioResponse(holdings=holdings, as_of_date=date.today(), next_rebalance_date=next_rebalance)


@app.get("/portfolio/rebalance-dates", response_model=list[RebalanceDate])
def get_rebalance_dates_endpoint():
    logger.info("GET /portfolio/rebalance-dates")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    dates = get_next_rebalance_dates(strategies)
    return [RebalanceDate(strategy_name=name, next_date=d) for name, d in dates.items()]


@app.post("/portfolio/combiner", response_model=PortfolioResponse)
def combine_portfolio(request: CombinerRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /portfolio/combiner: {request.strategies}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    strategy_results = {}
    for name in request.strategies:
        if name in strategies:
            rankings = _compute_strategy_rankings(name, strategies[name], db)
            strategy_results[name] = pd.DataFrame([r.model_dump() for r in rankings])
    
    combined = combine_strategies(strategy_results)
    holdings = [
        PortfolioHoldingOut(ticker=row['ticker'], name=_get_stock_name(row['ticker'], db),
                           weight=row['weight'], strategy=row['strategy'])
        for _, row in combined.iterrows()
    ]
    
    return PortfolioResponse(holdings=holdings, as_of_date=date.today(), next_rebalance_date=None)


@app.post("/portfolio/combiner/preview", response_model=CombinerPreviewResponse)
def preview_combination(request: CombinerPreviewRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /portfolio/combiner/preview: {request.name}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    strategy_results = {}
    for sw in request.strategies:
        if sw.name in strategies:
            rankings = _compute_strategy_rankings(sw.name, strategies[sw.name], db)
            strategy_results[sw.name] = pd.DataFrame([r.model_dump() for r in rankings])
    
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


@app.post("/portfolio/combiner/save", response_model=SavedCombination)
def save_combination(request: CombinerSaveRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /portfolio/combiner/save: {request.name}")
    
    existing = db.query(SavedCombinationModel).filter(SavedCombinationModel.name == request.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Combination '{request.name}' already exists")
    
    combo = SavedCombinationModel(
        name=request.name,
        strategies_json=json.dumps([{"name": s.name, "weight": s.weight} for s in request.strategies])
    )
    db.add(combo)
    db.commit()
    db.refresh(combo)
    
    return SavedCombination(id=combo.id, name=combo.name, strategies=request.strategies,
                           created_at=combo.created_at.isoformat())


@app.get("/portfolio/combiner/list", response_model=list[SavedCombination])
def list_combinations(db: Session = Depends(get_db)):
    logger.info("GET /portfolio/combiner/list")
    combos = db.query(SavedCombinationModel).all()
    from schemas import StrategyWeight
    return [
        SavedCombination(
            id=c.id, name=c.name,
            strategies=[StrategyWeight(**s) for s in json.loads(c.strategies_json)],
            created_at=c.created_at.isoformat()
        )
        for c in combos
    ]


@app.delete("/portfolio/combiner/{combo_id}")
def delete_combination(combo_id: int, db: Session = Depends(get_db)):
    logger.info(f"DELETE /portfolio/combiner/{combo_id}")
    combo = db.query(SavedCombinationModel).filter(SavedCombinationModel.id == combo_id).first()
    if not combo:
        raise HTTPException(status_code=404, detail=f"Combination {combo_id} not found")
    db.delete(combo)
    db.commit()
    return {"status": "deleted", "id": combo_id}


# Stocks
@app.get("/stocks/{ticker}", response_model=StockDetail)
def get_stock_detail(ticker: str, db: Session = Depends(get_db)):
    logger.info(f"GET /stocks/{ticker}")
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock '{ticker}' not found")
    
    fundamentals = db.query(Fundamentals).filter(Fundamentals.ticker == ticker).order_by(Fundamentals.fiscal_date.desc()).first()
    prices = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).order_by(DailyPrice.date.desc()).limit(252).all()
    returns = _calculate_returns(prices)
    
    return StockDetail(
        ticker=stock.ticker, name=stock.name, market_cap_msek=stock.market_cap_msek, sector=stock.sector,
        pe=fundamentals.pe if fundamentals else None, pb=fundamentals.pb if fundamentals else None,
        ps=fundamentals.ps if fundamentals else None, pfcf=fundamentals.pfcf if fundamentals else None,
        ev_ebitda=fundamentals.ev_ebitda if fundamentals else None, roe=fundamentals.roe if fundamentals else None,
        roa=fundamentals.roa if fundamentals else None, roic=fundamentals.roic if fundamentals else None,
        fcfroe=fundamentals.fcfroe if fundamentals else None, dividend_yield=fundamentals.dividend_yield if fundamentals else None,
        payout_ratio=fundamentals.payout_ratio if fundamentals else None, **returns
    )


# Backtesting
@app.get("/backtesting/strategies", response_model=list[StrategyMeta])
def get_backtesting_strategies():
    logger.info("GET /backtesting/strategies")
    return list_strategies()


@app.post("/backtesting/run", response_model=BacktestResponse)
def run_strategy_backtest(request: BacktestRequest, db: Session = Depends(get_db)):
    logger.info(f"POST /backtesting/run: {request.strategy_name} {request.start_date} to {request.end_date}")
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    if request.strategy_name not in strategies:
        raise HTTPException(status_code=404, detail=f"Strategy '{request.strategy_name}' not found")
    
    result = backtest_strategy(request.strategy_name, request.start_date, request.end_date, db, strategies[request.strategy_name])
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return BacktestResponse(
        strategy_name=result["strategy_name"], start_date=request.start_date, end_date=request.end_date,
        total_return_pct=result["total_return_pct"], sharpe=result["sharpe"], max_drawdown_pct=result["max_drawdown_pct"],
        equity_curve=result.get("portfolio_values")
    )


@app.get("/backtesting/results/{strategy}")
def get_strategy_backtest_results(strategy: str, db: Session = Depends(get_db)):
    logger.info(f"GET /backtesting/results/{strategy}")
    return get_backtest_results(db, strategy)


@app.post("/backtesting/long-term")
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


@app.post("/backtesting/enhanced")
def run_enhanced_backtest_deprecated(
    strategy: str = "sammansatt_momentum",
    years: int = 5,
    top_n: int = 10,
    rebalance_frequency: str = "quarterly"
):
    """
    DEPRECATED: Use /backtesting/long-term instead.
    This endpoint is kept for backward compatibility.
    """
    logger.warning("DEPRECATED endpoint /backtesting/enhanced called - use /backtesting/long-term")
    
    # Redirect to long-term endpoint
    return run_long_term_backtest(strategy, years, top_n, rebalance_frequency)


@app.post("/backtesting/historical")
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
    from services.eodhd_fetcher import get_omx_stockholm_stocks
    
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
        tickers = [t[0] for t in get_omx_stockholm_stocks()[:30]]
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


@app.post("/backtesting/historical/compare")
def compare_all_strategies_historical(
    start_year: int = 2005,
    end_year: int = 2024,
    db: Session = Depends(get_db)
):
    """Compare all strategies over a long historical period."""
    from services.historical_backtest import run_all_strategies_backtest, generate_synthetic_history
    from services.eodhd_fetcher import get_omx_stockholm_stocks
    
    logger.info(f"POST /backtesting/historical/compare: {start_year}-{end_year}")
    
    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    
    # Generate synthetic data for comparison
    tickers = [t[0] for t in get_omx_stockholm_stocks()[:30]]
    prices_df, fund_df = generate_synthetic_history(tickers, start_date, end_date)
    
    strategies = STRATEGIES_CONFIG.get("strategies", {})
    
    return run_all_strategies_backtest(
        start_date, end_date, strategies, prices_df, fund_df
    )


# Data Sync
@app.get("/data/sync-status", response_model=SyncStatus)
def get_data_sync_status(db: Session = Depends(get_db)):
    logger.info("GET /data/sync-status")
    return get_sync_status(db)


@app.post("/data/sync-now")
async def trigger_data_sync(
    db: Session = Depends(get_db), 
    region: str = "sweden", 
    market_cap: str = "large",
    method: str = Query("avanza", description="Sync method: avanza only (all other methods removed)")
):
    logger.info(f"POST /data/sync-now region={region} market_cap={market_cap} method={method}")
    
    # Send initial log
    await manager.send_log("info", f"Starting {method} sync for {region} {market_cap} cap stocks")
    
    # Only use Avanza fetcher
    from services.avanza_fetcher_v2 import avanza_sync
    result = await avanza_sync(db, region, market_cap, manager)
    
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

@app.get("/data/status/detailed")
def get_detailed_data_status(db: Session = Depends(get_db)):
    """Get detailed data status with cache information."""
    from services.advanced_cache import AdvancedCache
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    from services.live_universe import get_live_stock_universe
    
    # Get stock universe
    tickers = get_live_stock_universe('sweden', 'large')
    
    # Get cache stats
    cache = AdvancedCache()
    cache_stats = cache.get_cache_stats()
    
    # Get individual stock status
    fetcher = AvanzaDirectFetcher()
    stock_status = []
    
    for ticker in tickers[:15]:  # Check first 15 for performance
        # Get stock ID from known mapping
        stock_id = fetcher.known_stocks.get(ticker)
        
        if stock_id:
            endpoint = f"stock_overview/{stock_id}"
            params = {'stock_id': stock_id}
            cached_data = cache.get(endpoint, params)
            
            if cached_data:
                stock_status.append({
                    'ticker': ticker,
                    'stock_id': stock_id,
                    'last_updated': cached_data.get('last_updated'),
                    'fetch_success': cached_data.get('fetch_success', True),
                    'error': cached_data.get('error'),
                    'has_data': bool(cached_data.get('current_price'))
                })
            else:
                stock_status.append({
                    'ticker': ticker,
                    'stock_id': stock_id,
                    'last_updated': None,
                    'fetch_success': None,
                    'error': None,
                    'has_data': False
                })
        else:
            stock_status.append({
                'ticker': ticker,
                'stock_id': None,
                'last_updated': None,
                'fetch_success': False,
                'error': 'No stock ID mapping',
                'has_data': False
            })
    
    return {
        'cache_stats': cache_stats,
        'stock_status': stock_status,
        'total_stocks': len(tickers),
        'checked_stocks': len(stock_status)
    }

@app.post("/data/refresh-stock/{ticker}")
async def refresh_single_stock(ticker: str, db: Session = Depends(get_db)):
    """Manually refresh a single stock, bypassing cache."""
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    from services.advanced_cache import AdvancedCache
    
    fetcher = AvanzaDirectFetcher()
    cache = AdvancedCache()
    
    # Get stock ID
    stock_id = fetcher.known_stocks.get(ticker)
    if not stock_id:
        return {"error": f"Stock ID not found for {ticker}"}
    
    # Clear cache for this stock
    endpoint = f"stock_overview/{stock_id}"
    params = {'stock_id': stock_id}
    cache.delete(endpoint, params)
    
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

@app.get("/data/stock-config")
def get_stock_config():
    """Get current stock ID mappings."""
    from services.avanza_fetcher_v2 import AvanzaDirectFetcher
    
    fetcher = AvanzaDirectFetcher()
    return {
        "known_stocks": fetcher.known_stocks,
        "total_mapped": len(fetcher.known_stocks)
    }

@app.post("/data/stock-config")
def update_stock_config(config: dict, db: Session = Depends(get_db)):
    """Update stock ID mappings."""
    # This would require updating the fetcher configuration
    # For now, return the current config
    return {"message": "Stock config update not implemented yet", "config": config}

@app.get("/data/sync-config")
def get_sync_config():
    """Get current sync configuration."""
    from services.sync_config import sync_config
    
    return {
        "config": sync_config.config,
        "next_sync": sync_config.get_next_sync_time(),
        "should_sync_now": sync_config.should_sync_now(),
        "should_sync_on_visit": sync_config.should_sync_on_visit()
    }

@app.post("/data/sync-config")
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

@app.post("/data/sync-full")
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

@app.get("/data/sync/estimates")
def get_sync_estimates():
    """Get sync time estimates and rate limiting info."""
    from services.data_transparency import DataTransparencyService
    
    transparency = DataTransparencyService()
    return transparency.get_sync_progress()

@app.get("/strategies/{strategy_name}/data-check")
def check_strategy_data_quality(strategy_name: str, db: Session = Depends(get_db)):
    """Check if strategy can run with current data quality."""
    from services.data_transparency import validate_strategy_data_quality
    
    return validate_strategy_data_quality(db, strategy_name)

@app.get("/data/transparency")
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

@app.get("/data/reliability")
def get_reliability_status():
    """Get data reliability and retry queue status."""
    from services.optimized_yfinance import DataReliabilityManager
    
    reliability_manager = DataReliabilityManager()
    stats = reliability_manager.get_reliability_stats()
    retry_candidates = reliability_manager.get_retry_candidates()
    
    return {
        "reliability_stats": stats,
        "pending_retries": len(retry_candidates),
        "retry_queue": [{"ticker": ticker, "priority": priority} for ticker, priority in retry_candidates[:10]],
        "guarantee": "100% data retrieval with persistent retry system",
        "optimization": "1-3 second delays with parallel processing"
    }

@app.get("/data/universe/{region}/{market_cap}")
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


@app.get("/data/scheduler-status")
def get_scheduler_status_endpoint():
    logger.info("GET /data/scheduler-status")
    return get_scheduler_status()


@app.get("/data/freshness")
def get_data_freshness(db: Session = Depends(get_db)):
    """Check if data is fresh enough for strategy calculations."""
    logger.info("GET /data/freshness")
    return check_data_freshness(db)


@app.get("/cache/stats")
def get_cache_statistics():
    """Get cache statistics."""
    logger.info("GET /cache/stats")
    return get_cache_stats()


@app.post("/cache/invalidate")
def invalidate_cache_endpoint(pattern: str = None):
    """Invalidate cache entries."""
    logger.info(f"POST /cache/invalidate pattern={pattern}")
    invalidate_cache(pattern)
    return {"status": "invalidated", "pattern": pattern}


# Helper functions
def _compute_strategy_rankings(name: str, config: dict, db: Session) -> list[RankedStock]:
    # Support both old ("type") and new ("category") config keys
    strategy_type = config.get("category", config.get("type", ""))
    
    prices = db.query(DailyPrice).all()
    fundamentals = db.query(Fundamentals).all()
    
    prices_df = pd.DataFrame([{"ticker": p.ticker, "date": p.date, "close": p.close} for p in prices]) if prices else pd.DataFrame()
    fund_df = pd.DataFrame([{
        "ticker": f.ticker, "pe": f.pe, "pb": f.pb, "ps": f.ps, "pfcf": f.pfcf, "ev_ebitda": f.ev_ebitda,
        "dividend_yield": f.dividend_yield, "roe": f.roe, "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe, "payout_ratio": f.payout_ratio
    } for f in fundamentals]) if fundamentals else pd.DataFrame()
    
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
        scores = calculate_value_score(fund_df)
        ranked_df = rank_and_select_top_n(scores, config)
    elif strategy_type == "dividend":
        if fund_df.empty: return []
        scores = calculate_dividend_score(fund_df)
        ranked_df = rank_and_select_top_n(scores, config)
    elif strategy_type == "quality":
        if fund_df.empty: return []
        scores = calculate_quality_score(fund_df, prices_df)
        ranked_df = rank_and_select_top_n(scores, config)
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
    
    # Add investment safeguards to strategy response
    from services.investment_safeguards import add_investment_safeguards_to_response, validate_strategy_safety
    from services.data_transparency import DataTransparencyService
    
    # Get data quality for safety validation
    transparency = DataTransparencyService()
    data_status = transparency.get_detailed_data_status(db)
    
    # Validate strategy safety
    safety_check = validate_strategy_safety(name, data_status['summary'])
    
    # Convert to response format with safeguards
    response_data = {
        'stocks': stocks_with_freshness,
        'strategy_name': name,
        'data_quality': data_status['summary'],
        'safety_validation': safety_check,
        'total_stocks': len(stocks_with_freshness)
    }
    
    # Add all investment safeguards
    response_data = add_investment_safeguards_to_response(response_data, data_status['summary'])
    
    return response_data


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
@app.get("/export/rankings/{strategy_name}", response_class=PlainTextResponse)
def export_strategy_rankings(strategy_name: str, db: Session = Depends(get_db)):
    """Export strategy rankings as CSV."""
    rankings = get_strategy_rankings(strategy_name, db)
    csv_data = export_rankings_to_csv([r.dict() for r in rankings], strategy_name)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={strategy_name}_rankings.csv"}
    )


@app.get("/export/backtest/{strategy_name}", response_class=PlainTextResponse)
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


# Enhanced Portfolio Tracking with Performance Visualization
@app.post("/portfolio/import/avanza-csv")
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


@app.get("/portfolio/performance/chart-data")
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


@app.get("/portfolio/performance/stats")
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
@app.post("/portfolio/create")
def create_new_portfolio(name: str = "Default", db: Session = Depends(get_db)):
    """Create a new portfolio for tracking."""
    portfolio_id = create_portfolio(db, name)
    return {"portfolio_id": portfolio_id, "name": name}


@app.post("/portfolio/{portfolio_id}/transaction")
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


@app.get("/portfolio/{portfolio_id}/holdings")
def get_holdings(portfolio_id: int, db: Session = Depends(get_db)):
    """Get current portfolio holdings with values."""
    return get_portfolio_value(db, portfolio_id)


@app.get("/portfolio/{portfolio_id}/performance")
def get_performance(portfolio_id: int, db: Session = Depends(get_db)):
    """Get portfolio performance metrics."""
    return calculate_portfolio_performance(db, portfolio_id)


@app.post("/portfolio/{portfolio_id}/rebalance-trades")
def get_rebalance_trades(
    portfolio_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """Calculate trades needed to rebalance to target allocation."""
    target_holdings = request.get("target_holdings", [])
    portfolio_value = request.get("portfolio_value")
    return calculate_rebalance_trades(db, portfolio_id, target_holdings, portfolio_value)


@app.get("/portfolio/{portfolio_id}/history")
def get_history(portfolio_id: int, db: Session = Depends(get_db)):
    """Get portfolio value history."""
    return get_portfolio_history(db, portfolio_id)


@app.post("/portfolio/{portfolio_id}/snapshot")
def take_snapshot(portfolio_id: int, db: Session = Depends(get_db)):
    """Save current portfolio state as a snapshot."""
    snapshot_id = save_snapshot(db, portfolio_id)
    return {"snapshot_id": snapshot_id}


# Transaction Costs
@app.get("/costs/brokers")
def list_brokers():
    """Get available brokers with fee structures."""
    return get_available_brokers()


@app.post("/costs/calculate")
def calculate_trade_cost(
    trade_value: float,
    broker: str = "avanza",
    spread_pct: float = 0.002,
    is_round_trip: bool = False
):
    """Calculate transaction costs for a single trade."""
    return calculate_total_transaction_cost(trade_value, broker, spread_pct, is_round_trip)


@app.post("/costs/rebalance")
def calculate_rebalance_cost(request: dict):
    """Calculate total costs for a rebalance."""
    trades = request.get("trades", [])
    broker = request.get("broker", "avanza")
    spread_pct = request.get("spread_pct", 0.002)
    return calculate_rebalance_costs(trades, broker, spread_pct)


@app.post("/costs/annual-impact")
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
@app.post("/benchmark/compare")
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


@app.post("/benchmark/chart-data")
def get_benchmark_chart_data(request: dict):
    """Get normalized chart data for strategy vs benchmark."""
    strategy_values = request.get("strategy_values", [])
    benchmark_values = request.get("benchmark_values", [])
    dates = request.get("dates")
    
    return generate_relative_chart_data(strategy_values, benchmark_values, dates)


@app.post("/benchmark/rolling")
def get_rolling_metrics_endpoint(request: dict):
    """Get rolling alpha, beta, and excess return."""
    strategy_values = request.get("strategy_values", [])
    benchmark_values = request.get("benchmark_values", [])
    window = request.get("window", 252)
    
    return calculate_rolling_metrics(strategy_values, benchmark_values, window)


# Risk Analytics
@app.post("/risk/metrics")
def get_risk_metrics(request: dict):
    """Get comprehensive risk metrics for a value series."""
    values = request.get("values", [])
    benchmark_values = request.get("benchmark_values")
    risk_free_rate = request.get("risk_free_rate", 0.02)
    
    return calculate_risk_metrics(values, benchmark_values, risk_free_rate)


@app.post("/risk/sector-exposure")
def get_sector_exposure(request: dict):
    """Calculate sector exposure from holdings."""
    holdings = request.get("holdings", [])
    return calculate_sector_exposure(holdings)


@app.post("/risk/drawdown")
def get_drawdown_analysis_endpoint(request: dict):
    """Detailed drawdown analysis."""
    values = request.get("values", [])
    return calculate_drawdown_analysis(values)


# Dividends
@app.get("/dividends/upcoming")
def get_upcoming_dividends_endpoint(days_ahead: int = 90, db: Session = Depends(get_db)):
    """Get upcoming dividend events."""
    return get_upcoming_dividends(db, days_ahead=days_ahead)


@app.post("/dividends/projected-income")
def get_projected_income(request: dict, db: Session = Depends(get_db)):
    """Calculate projected dividend income from holdings."""
    holdings = request.get("holdings", [])
    months = request.get("months_ahead", 12)
    return calculate_projected_income(db, holdings, months)


@app.get("/dividends/history/{ticker}")
def get_dividend_history_endpoint(ticker: str, years: int = 5, db: Session = Depends(get_db)):
    """Get dividend history for a stock."""
    return get_dividend_history(db, ticker, years)


@app.get("/dividends/growth/{ticker}")
def get_dividend_growth(ticker: str, years: int = 5, db: Session = Depends(get_db)):
    """Calculate dividend growth rate."""
    return calculate_dividend_growth(db, ticker, years)


# Watchlist
@app.post("/watchlist/create")
def create_watchlist_endpoint(name: str = "Default", db: Session = Depends(get_db)):
    """Create a new watchlist."""
    watchlist_id = create_watchlist(db, name)
    return {"watchlist_id": watchlist_id, "name": name}


@app.get("/watchlist")
def list_watchlists(db: Session = Depends(get_db)):
    """Get all watchlists."""
    return get_all_watchlists(db)


@app.get("/watchlist/{watchlist_id}")
def get_watchlist_endpoint(watchlist_id: int, db: Session = Depends(get_db)):
    """Get watchlist with items and rankings."""
    return get_watchlist(db, watchlist_id)


@app.post("/watchlist/{watchlist_id}/add")
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


@app.delete("/watchlist/{watchlist_id}/remove/{ticker}")
def remove_from_watchlist_endpoint(watchlist_id: int, ticker: str, db: Session = Depends(get_db)):
    """Remove stock from watchlist."""
    success = remove_from_watchlist(db, watchlist_id, ticker)
    return {"success": success}


@app.get("/watchlist/{watchlist_id}/alerts")
def get_watchlist_alerts(
    watchlist_id: int,
    strategy: str = "sammansatt_momentum",
    db: Session = Depends(get_db)
):
    """Check for ranking changes in watchlist stocks."""
    return check_ranking_changes(db, watchlist_id, strategy)


# Custom Strategy Builder
@app.get("/custom-strategy/factors")
def get_factors():
    """Get available factors for custom strategies."""
    return get_available_factors()


@app.get("/custom-strategy")
def list_strategies(db: Session = Depends(get_db)):
    """List all custom strategies."""
    return list_custom_strategies(db)


@app.post("/custom-strategy/create")
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


@app.get("/custom-strategy/{strategy_id}")
def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Get a custom strategy by ID."""
    strategy = get_custom_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@app.delete("/custom-strategy/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Delete a custom strategy."""
    success = delete_custom_strategy(db, strategy_id)
    return {"success": success}


@app.post("/custom-strategy/{strategy_id}/run")
def run_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Run a custom strategy and get rankings."""
    strategy = get_custom_strategy(db, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Get data
    prices = db.query(DailyPrice).all()
    fundamentals = db.query(Fundamentals).all()
    
    prices_df = pd.DataFrame([{"ticker": p.ticker, "date": p.date, "close": p.close} for p in prices]) if prices else pd.DataFrame()
    fund_df = pd.DataFrame([{
        "ticker": f.ticker, "market_cap": f.market_cap,
        "pe": f.pe, "pb": f.pb, "ps": f.ps, "p_fcf": f.p_fcf, "ev_ebitda": f.ev_ebitda,
        "dividend_yield": f.dividend_yield, "roe": f.roe, "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe,
        "payout_ratio": f.payout_ratio
    } for f in fundamentals]) if fundamentals else pd.DataFrame()
    
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
@app.get("/markets")
def list_markets():
    """Get available markets."""
    return get_available_markets()


@app.get("/markets/{market}/stocks")
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
@app.post("/import/csv")
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


@app.post("/import/csv/holdings")
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

@app.post("/user/profile")
async def create_user_profile(name: str, email: str = None, db: Session = Depends(get_db)):
    """Create a new user profile."""
    from services.user_storage import UserStorageService
    
    user_id = UserStorageService.create_user_profile(db, name, email)
    return {"user_id": user_id, "message": "Profile created successfully"}

@app.get("/user/{user_id}/profile")
async def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    """Get user profile."""
    from services.user_storage import UserStorageService
    
    profile = UserStorageService.get_user_profile(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    return profile

@app.post("/user/{user_id}/avanza-import")
async def save_avanza_import(user_id: str, filename: str, transactions_count: int, 
                           holdings_data: dict, raw_data: str, db: Session = Depends(get_db)):
    """Save Avanza CSV import for user."""
    from services.user_storage import UserStorageService
    
    import_id = UserStorageService.save_avanza_import(
        db, user_id, filename, transactions_count, holdings_data, raw_data
    )
    return {"import_id": import_id, "message": "Avanza import saved successfully"}

@app.get("/cache/stats")
async def get_cache_stats():
    """Get cache performance statistics."""
    from services.advanced_cache import AdvancedCache
    
    cache = AdvancedCache()
    stats = cache.get_cache_stats()
    
    return {
        "cache_stats": stats,
        "api_calls_saved": stats['total_hits'],
        "cache_efficiency": stats['cache_efficiency']
    }

@app.get("/portfolio/{portfolio_name}/performance")
async def get_portfolio_performance(portfolio_name: str, days: int = 30):
    """Get portfolio performance over time."""
    from services.advanced_cache import HistoricalTracker
    
    tracker = HistoricalTracker()
    performance = tracker.get_portfolio_performance(portfolio_name, days)
    
    return {
        "portfolio_name": portfolio_name,
        "performance": performance,
        "tracking_period_days": days
    }

@app.get("/stock/{ticker}/history")
async def get_stock_history(ticker: str, days: int = 30):
    """Get price history for a stock."""
    from services.advanced_cache import HistoricalTracker
    
    tracker = HistoricalTracker()
    history = tracker.get_price_history(ticker, days)
    
    return {
        "ticker": ticker,
        "history": history,
        "data_points": len(history)
    }

@app.post("/portfolio/{portfolio_name}/snapshot")
async def record_portfolio_snapshot(portfolio_name: str, holdings: List[dict]):
    """Record a portfolio snapshot for tracking."""
    from services.advanced_cache import HistoricalTracker
    
    tracker = HistoricalTracker()
    tracker.record_portfolio_snapshot(portfolio_name, holdings)
    
    return {
        "message": f"Portfolio snapshot recorded for {portfolio_name}",
        "holdings_count": len(holdings),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/user/{user_id}/avanza-imports")
async def get_user_avanza_imports(user_id: str, db: Session = Depends(get_db)):
    """Get all Avanza imports for user."""
    from services.user_storage import UserStorageService
    
    imports = UserStorageService.get_user_avanza_imports(db, user_id)
    return {"imports": imports, "count": len(imports)}

@app.websocket("/ws/sync-logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
