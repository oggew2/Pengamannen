from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from contextlib import asynccontextmanager
import pandas as pd
import json
import logging

from backend.db import get_db, engine, Base, text
from backend.models import Stock, DailyPrice, Fundamentals, SavedCombination as SavedCombinationModel
from backend.schemas import (
    StrategyMeta, RankedStock, StockDetail, 
    PortfolioResponse, PortfolioHoldingOut, RebalanceDate,
    BacktestRequest, BacktestResponse, SyncStatus, CombinerRequest,
    CombinerPreviewRequest, CombinerPreviewResponse, CombinerSaveRequest, SavedCombination
)
from backend.services.ranking import (
    calculate_momentum_score, calculate_momentum_with_quality_filter,
    calculate_value_score, calculate_dividend_score, calculate_quality_score,
    rank_and_select_top_n
)
from backend.services.portfolio import get_next_rebalance_dates, combine_strategies
from backend.services.eodhd_fetcher import sync_all_stocks, get_sync_status
from backend.services.backtesting import backtest_strategy, get_backtest_results
from backend.services.validation import check_data_freshness
from backend.services.cache import invalidate_cache, get_cache_stats
from backend.config.settings import get_settings, load_strategies_config
from backend.jobs.scheduler import start_scheduler, stop_scheduler, get_scheduler_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    from backend.schemas import StrategyWeight
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
    from backend.services.historical_backtest import run_historical_backtest, generate_synthetic_history
    from backend.services.eodhd_fetcher import get_omx_stockholm_stocks
    
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
    from backend.services.historical_backtest import run_all_strategies_backtest, generate_synthetic_history
    from backend.services.eodhd_fetcher import get_omx_stockholm_stocks
    
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
def trigger_data_sync(db: Session = Depends(get_db), full_refresh: bool = False):
    logger.info(f"POST /data/sync-now full_refresh={full_refresh}")
    settings = get_settings()
    if not settings.eodhd_api_key:
        raise HTTPException(status_code=400, detail="EODHD_API_KEY not configured")
    
    result = sync_all_stocks(settings.eodhd_api_key, db, full_refresh=full_refresh)
    return {"status": "syncing" if not result.get("rate_limit_hit") else "rate_limited", **result}


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
    
    return [RankedStock(ticker=row['ticker'], name=_get_stock_name(row['ticker'], db),
                        rank=int(row['rank']), score=float(row['score'])) for _, row in ranked_df.iterrows()]


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
