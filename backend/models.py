from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text, Boolean, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db import Base
import hashlib
import secrets

class User(Base):
    """User account for multi-user support."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    name = Column(String)
    created_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    invite_code = Column(String, unique=True, nullable=True)  # Code others use to register
    market_filter = Column(String, default="stockholmsborsen")  # stockholmsborsen, first_north, both
    
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        return self.password_hash == self.hash_password(password)
    
    @staticmethod
    def generate_invite_code() -> str:
        return secrets.token_urlsafe(8)


class UserSession(Base):
    """User session tokens."""
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)
    
    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)


class Stock(Base):
    __tablename__ = "stocks"
    ticker = Column(String, primary_key=True)
    name = Column(String)
    isin = Column(String)
    avanza_id = Column(String, index=True)  # Avanza stock ID for API calls
    market_cap_msek = Column(Float)
    sector = Column(String)
    market = Column(String, default="stockholmsborsen")  # stockholmsborsen, first_north, helsinki, oslo, copenhagen
    country = Column(String, default="sweden")  # sweden, finland, norway, denmark
    currency = Column(String, default="SEK")  # SEK, EUR, NOK, DKK
    stock_type = Column(String, default="stock")  # stock, etf_certificate, preference, sdb
    is_active = Column(Boolean, default=True)  # False if delisted or no longer on Avanza
    last_validated = Column(Date)  # Last time we verified stock exists on Avanza
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

class DailyPrice(Base):
    __tablename__ = "daily_prices"
    ticker = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    close = Column(Float)
    high = Column(Float)
    low = Column(Float)
    volume = Column(Float)

class IndexPrice(Base):
    """Historical index prices (OMXS30, etc). Stored separately since indices aren't stocks."""
    __tablename__ = "index_prices"
    index_id = Column(String, primary_key=True)  # e.g., "OMXS30"
    date = Column(Date, primary_key=True)
    close = Column(Float)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)

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
    # TradingView pre-calculated momentum
    perf_1m = Column(Float)
    perf_3m = Column(Float)
    perf_6m = Column(Float)
    perf_12m = Column(Float)
    # TradingView pre-calculated F-Score
    piotroski_f_score = Column(Integer)
    # Data source tracking
    data_source = Column(String, default='avanza')

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
    __table_args__ = (
        UniqueConstraint('name', 'user_id', name='uq_saved_combinations_name_user'),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)  # Optional for backwards compat
    name = Column(String)
    strategies_json = Column(Text)
    created_at = Column(DateTime, default=func.now())


class UserPortfolio(Base):
    """Track user's actual portfolio holdings over time."""
    __tablename__ = "user_portfolios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String, default="Default")
    description = Column(Text)
    holdings = Column(Text)  # JSON string of holdings
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AvanzaImport(Base):
    """Store Avanza CSV imports per user."""
    __tablename__ = "avanza_imports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    filename = Column(String)
    import_date = Column(DateTime, default=func.now())
    transactions_count = Column(Integer)
    holdings_json = Column(Text)  # Processed holdings
    raw_csv = Column(Text)  # Original CSV for re-processing
    status = Column(String, default="active")


class PortfolioTransaction(Base):
    """Track buy/sell transactions."""
    __tablename__ = "portfolio_transactions_v2"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    portfolio_id = Column(Integer, index=True)
    ticker = Column(String, index=True)
    transaction_type = Column(String)  # BUY, SELL, DIVIDEND
    shares = Column(Float)
    price = Column(Float)
    fees = Column(Float, default=0)
    transaction_date = Column(Date)
    strategy = Column(String)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())


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
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
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


class UserGoal(Base):
    """User financial goals."""
    __tablename__ = "user_goals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    name = Column(String)
    target_amount = Column(Float)
    current_amount = Column(Float)
    monthly_contribution = Column(Float, default=0)
    target_date = Column(Date)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RebalanceHistory(Base):
    """Track rebalance events."""
    __tablename__ = "rebalance_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String, index=True)
    rebalance_date = Column(Date, index=True)
    trades_json = Column(Text)  # JSON: [{ticker, action, shares, amount}]
    total_cost = Column(Float)
    portfolio_value = Column(Float)
    created_at = Column(DateTime, default=func.now())


class UserPortfolioAccount(Base):
    """User portfolio accounts (ISK, KF, etc)."""
    __tablename__ = "user_portfolio_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)  # "ISK 1", "KF Pension", etc
    account_type = Column(String)  # ISK, KF, AF, Depot
    strategy = Column(String)  # sammansatt_momentum, etc
    holdings_json = Column(Text)  # JSON: [{ticker, shares, avg_price}]
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RankingsSnapshot(Base):
    """Historical rankings snapshots."""
    __tablename__ = "rankings_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String, index=True)
    snapshot_date = Column(Date, index=True)
    rankings_json = Column(Text)  # JSON: [{ticker, rank, score}]
    created_at = Column(DateTime, default=func.now())


class FundamentalsSnapshot(Base):
    """Historical fundamentals for backtesting and verification."""
    __tablename__ = "fundamentals_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, index=True)
    ticker = Column(String, index=True)
    market_cap = Column(Float)
    pe = Column(Float)
    pb = Column(Float)
    ps = Column(Float)
    p_fcf = Column(Float)
    ev_ebitda = Column(Float)
    roe = Column(Float)
    roa = Column(Float)
    roic = Column(Float)
    fcfroe = Column(Float)
    dividend_yield = Column(Float)
    payout_ratio = Column(Float)
    # Composite index for efficient date+ticker lookups
    __table_args__ = (
        Index('idx_fund_snapshot_date_ticker', 'snapshot_date', 'ticker'),
    )


class SyncLog(Base):
    """Track data sync operations for monitoring and alerting."""
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    sync_type = Column(String, default="full")  # full, prices, fundamentals, rankings
    success = Column(Boolean, default=True)
    duration_seconds = Column(Float)
    stocks_updated = Column(Integer, default=0)
    prices_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    details_json = Column(Text, nullable=True)  # JSON with additional details


class DataAlert(Base):
    """Historical log of data integrity alerts."""
    __tablename__ = "data_alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now(), index=True)
    severity = Column(String, index=True)  # CRITICAL, WARNING
    alert_type = Column(String, index=True)  # STALE_DATA, LOW_COVERAGE, SYNC_FAILED, etc.
    message = Column(Text)
    details_json = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    notified = Column(Boolean, default=False)  # Email sent?


class BandingHolding(Base):
    """Track current holdings for banding strategy.
    
    Banding rules (from Börslabbet):
    - Buy: Top 10 stocks by momentum
    - Sell: Only when stock falls below rank 20
    - This reduces turnover while maintaining returns
    """
    __tablename__ = "banding_holdings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String, index=True)  # e.g., 'nordic_sammansatt_momentum'
    ticker = Column(String, index=True)
    entry_rank = Column(Integer)  # Rank when added
    entry_date = Column(Date)
    current_rank = Column(Integer)  # Updated daily
    last_updated = Column(Date)
    is_active = Column(Boolean, default=True)  # False when sold
    exit_date = Column(Date, nullable=True)
    exit_rank = Column(Integer, nullable=True)
