from pydantic import BaseModel
from datetime import date
from typing import Optional

class StockBase(BaseModel):
    ticker: str
    name: Optional[str] = None
    market_cap_msek: Optional[float] = None
    sector: Optional[str] = None

class StockDetail(StockBase):
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    pfcf: Optional[float] = None
    ev_ebitda: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None
    fcfroe: Optional[float] = None
    dividend_yield: Optional[float] = None
    payout_ratio: Optional[float] = None
    return_1m: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None
    return_12m: Optional[float] = None

class RankedStock(BaseModel):
    ticker: str
    name: Optional[str] = None
    rank: int
    score: float
    last_updated: Optional[str] = None
    data_age_days: Optional[int] = None
    freshness: Optional[str] = None  # "fresh", "stale", "very_stale", "no_data"

class StrategyMeta(BaseModel):
    name: str
    display_name: str
    description: str
    type: str
    portfolio_size: int
    rebalance_frequency: str

class PortfolioHoldingOut(BaseModel):
    ticker: str
    name: Optional[str] = None
    weight: float
    strategy: str

class PortfolioResponse(BaseModel):
    holdings: list[PortfolioHoldingOut]
    as_of_date: date
    next_rebalance_date: Optional[date] = None

class RebalanceDate(BaseModel):
    strategy_name: str
    next_date: date

class BacktestRequest(BaseModel):
    strategy_name: str
    start_date: date
    end_date: date

class BacktestResponse(BaseModel):
    strategy_name: str
    start_date: date
    end_date: date
    total_return_pct: float
    sharpe: float
    max_drawdown_pct: float
    equity_curve: Optional[list] = None

class SyncStatus(BaseModel):
    stocks: int
    prices: int
    fundamentals: int
    latest_price_date: Optional[str] = None
    latest_fundamental_date: Optional[str] = None

class CombinerRequest(BaseModel):
    strategies: list[str]
    weights: Optional[list[float]] = None

# New schemas for combiner
class StrategyWeight(BaseModel):
    name: str
    weight: float

class CombinerPreviewRequest(BaseModel):
    name: str
    strategies: list[StrategyWeight]

class CombinerPreviewResponse(BaseModel):
    total_stocks: int
    holdings: list[PortfolioHoldingOut]
    overlaps: list[str]

class SavedCombination(BaseModel):
    id: int
    name: str
    strategies: list[StrategyWeight]
    created_at: str

class CombinerSaveRequest(BaseModel):
    name: str
    strategies: list[StrategyWeight]
