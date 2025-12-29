from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text
from sqlalchemy.sql import func
from backend.db import Base

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
    pe = Column(Float)
    pb = Column(Float)
    ps = Column(Float)
    pfcf = Column(Float)
    ev_ebitda = Column(Float)
    roe = Column(Float)
    roa = Column(Float)
    roic = Column(Float)
    fcfroe = Column(Float)
    dividend_yield = Column(Float)
    payout_ratio = Column(Float)
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
