from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text
from sqlalchemy.sql import func
from db import Base

class Stock(Base):
    __tablename__ = "stocks"
    ticker = Column(String, primary_key=True)
    name = Column(String)
    market_cap_msek = Column(Float)
    sector = Column(String)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

class DailyPrice(Base):
    __tablename__ = "daily_prices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Float)

class Fundamentals(Base):
    __tablename__ = "fundamentals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    fiscal_date = Column(Date)
    market_cap = Column(Float)  # Market cap in SEK
    pe = Column(Float)
    pb = Column(Float)
    ps = Column(Float)
    p_fcf = Column(Float)  # Price/Free Cash Flow
    ev_ebitda = Column(Float)
    roe = Column(Float)
    roa = Column(Float)
    roic = Column(Float)
    fcfroe = Column(Float)
    dividend_yield = Column(Float)
    payout_ratio = Column(Float)
    # Piotroski F-Score components
    net_income = Column(Float)
    operating_cf = Column(Float)
    total_assets = Column(Float)
    long_term_debt = Column(Float)
    current_ratio = Column(Float)
    shares_outstanding = Column(Float)
    gross_margin = Column(Float)
    asset_turnover = Column(Float)
    fetched_date = Column(Date)

class StrategySignal(Base):
    __tablename__ = "strategy_signals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String, index=True)
    ticker = Column(String, index=True)
    rank = Column(Integer)
    score = Column(Float)
    calculated_date = Column(Date)

class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String, index=True)
    ticker = Column(String, index=True)
    weight = Column(Float)
    as_of_date = Column(Date)

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String, index=True)
    start_date = Column(Date)
    end_date = Column(Date)
    total_return_pct = Column(Float)
    sharpe = Column(Float)
    max_drawdown_pct = Column(Float)
    json_data = Column(Text)

class SavedCombination(Base):
    __tablename__ = "saved_combinations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    strategies_json = Column(Text)
    created_at = Column(DateTime, default=func.now())


class UserPortfolio(Base):
    """Track user's actual portfolio holdings over time."""
    __tablename__ = "user_portfolios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, default="Default")
    created_at = Column(DateTime, default=func.now())


class PortfolioTransaction(Base):
    """Track buy/sell transactions."""
    __tablename__ = "portfolio_transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, index=True)
    ticker = Column(String, index=True)
    transaction_type = Column(String)  # BUY, SELL
    shares = Column(Float)
    price = Column(Float)
    fees = Column(Float, default=0)
    transaction_date = Column(Date)
    strategy = Column(String)
    notes = Column(Text)


class PortfolioSnapshot(Base):
    """Daily portfolio value snapshots for performance tracking."""
    __tablename__ = "portfolio_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, index=True)
    snapshot_date = Column(Date, index=True)
    total_value = Column(Float)
    cash = Column(Float)
    holdings_json = Column(Text)  # JSON of {ticker: {shares, value, weight}}


class DividendEvent(Base):
    """Track dividend events for stocks."""
    __tablename__ = "dividend_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, index=True)
    ex_date = Column(Date, index=True)
    payment_date = Column(Date)
    amount = Column(Float)  # Per share
    currency = Column(String, default="SEK")
    dividend_type = Column(String, default="regular")  # regular, special


class Watchlist(Base):
    """User watchlist for tracking stocks."""
    __tablename__ = "watchlists"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, default="Default")
    created_at = Column(DateTime, default=func.now())


class WatchlistItem(Base):
    """Items in a watchlist."""
    __tablename__ = "watchlist_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    watchlist_id = Column(Integer, index=True)
    ticker = Column(String, index=True)
    added_at = Column(DateTime, default=func.now())
    notes = Column(Text)
    alert_on_ranking_change = Column(Integer, default=1)  # 1=True


class CustomStrategy(Base):
    """User-defined custom strategies."""
    __tablename__ = "custom_strategies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    description = Column(Text)
    factors_json = Column(Text)  # JSON: [{factor, weight, direction}]
    filters_json = Column(Text)  # JSON: [{field, operator, value}]
    rebalance_frequency = Column(String, default="quarterly")
    position_count = Column(Integer, default=10)
    created_at = Column(DateTime, default=func.now())
