"""
Ranking service - Börslabbet strategy scoring functions.

Verified Strategy Rules (from börslabbet.se/borslabbets-strategier):
- Universe: Minimum 2B SEK market cap (since June 2023)
- Universe: Top 40% by market cap (for liquidity)
- Universe: Swedish stocks only (excludes Norwegian stocks ending with 'O')
- Excludes: Financial companies (nyckeltal don't apply well)
- Piotroski F-Score: 0-9 scale quality filter
- Trendande strategies: Top 40% by primary factor, then top 25% by momentum
- Banding: For momentum, only sell if stock drops out of top 20%
"""
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Minimum market cap threshold (2 billion SEK since June 2023)
MIN_MARKET_CAP_MSEK = 2000  # 2B SEK = 2000 MSEK

# Minimum dividend yield for Trendande Utdelning (Börslabbet uses ~3%)
MIN_DIVIDEND_YIELD = 3.0

# Valid stock types for strategy calculations (excludes ETFs, certificates, etc.)
VALID_STOCK_TYPES = ['stock', 'sdb']  # Regular stocks and Swedish Depository Receipts

# Norwegian stock suffixes to exclude (Börslabbet focuses on Swedish stocks)
# These are Oslo Børs stocks that appear in TradingView Sweden scan
NORWEGIAN_SUFFIXES = ['O', 'OO']  # e.g., EQNRO, NHYO, MOBAOO

# Financial sectors to exclude (nyckeltal don't apply well to these)
# Swedish names (from Avanza) and English names (from TradingView)
FINANCIAL_SECTORS = [
    # Swedish names (Avanza)
    'Traditionell Bankverksamhet',
    'Investmentbolag',
    'Försäkring',
    'Sparande & Investering',
    'Kapitalförvaltning',
    'Konsumentkredit',
    # English names (TradingView) - "Finance" covers all financial companies
    'Finance',
]

# For momentum strategy - Börslabbet INCLUDES Investmentbolag
# But TradingView's "Finance" sector includes everything, so we need to be more selective
# We'll exclude Finance but note that this excludes Investmentbolag too
# (TradingView doesn't distinguish between banks and investment companies)
FINANCIAL_SECTORS_MOMENTUM = [
    # Swedish names (Avanza)
    'Traditionell Bankverksamhet',
    'Försäkring',
    'Sparande & Investering',
    'Kapitalförvaltning',
    'Konsumentkredit',
    # English names (TradingView)
    'Finance',  # Note: This excludes Investmentbolag too, but necessary for Nordic
]


def filter_norwegian_stocks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter out Norwegian stocks (Oslo Børs) from Swedish universe.
    Norwegian tickers typically end with 'O' or 'OO' (e.g., EQNRO, NHYO, MOBAOO).
    """
    if df.empty or 'ticker' not in df.columns:
        return df
    
    def is_swedish(ticker):
        # Extract base ticker without exchange prefix
        base = ticker.split(':')[-1] if ':' in ticker else ticker
        # Check if ends with Norwegian suffix
        for suffix in NORWEGIAN_SUFFIXES:
            if base.endswith(suffix) and len(base) > len(suffix):
                return False
        return True
    
    return df[df['ticker'].apply(is_swedish)]


def filter_real_stocks(df: pd.DataFrame, include_preference: bool = False) -> pd.DataFrame:
    """Filter out ETFs, certificates, and leveraged products."""
    if df.empty or 'stock_type' not in df.columns:
        return df
    valid_types = VALID_STOCK_TYPES + (['preference'] if include_preference else [])
    
    # CRITICAL FIX: Handle categorical columns that don't have .str accessor
    if df['stock_type'].dtype.name == 'category':
        # Convert categories to lowercase for comparison
        valid_types_lower = [t.lower() for t in valid_types]
        return df[df['stock_type'].astype(str).str.lower().isin(valid_types_lower)]
    else:
        # Case-insensitive comparison for non-categorical
        return df[df['stock_type'].str.lower().isin([t.lower() for t in valid_types])]


def filter_financial_companies(df: pd.DataFrame, for_momentum: bool = False) -> pd.DataFrame:
    """
    Exclude financial companies where valuation metrics don't apply well.
    
    Args:
        df: DataFrame with 'sector' column
        for_momentum: If True, use FINANCIAL_SECTORS_MOMENTUM (includes Investmentbolag)
    """
    if df.empty or 'sector' not in df.columns:
        return df
    
    # Use appropriate sector list
    sectors_to_exclude = FINANCIAL_SECTORS_MOMENTUM if for_momentum else FINANCIAL_SECTORS
    financial_lower = [s.lower() for s in sectors_to_exclude]
    
    if df['sector'].dtype.name == 'category':
        sector_lower = df['sector'].astype(str).str.lower()
        sector_lower = sector_lower.fillna('unknown')
        return df[~sector_lower.isin(financial_lower)]
    else:
        return df[~df['sector'].fillna('').str.lower().isin(financial_lower)]


def filter_by_min_market_cap(df: pd.DataFrame, min_cap_msek: float = MIN_MARKET_CAP_MSEK) -> pd.DataFrame:
    """Filter stocks below minimum market cap threshold (2B SEK since June 2023)."""
    if df.empty or 'market_cap' not in df.columns:
        return df
    return df[df['market_cap'] >= min_cap_msek]


def filter_by_market_cap(fund_df: pd.DataFrame, percentile: float = None) -> pd.DataFrame:
    """
    Filter stocks by market cap using fixed 2B SEK threshold.
    
    Note: The percentile parameter is kept for backward compatibility but ignored.
    Börslabbet uses a fixed 2B SEK minimum, not a percentile-based threshold.
    """
    if fund_df.empty or 'market_cap' not in fund_df.columns:
        return fund_df
    # Use fixed 2B SEK threshold (Börslabbet's rule since June 2023)
    return fund_df[fund_df['market_cap'] >= MIN_MARKET_CAP_MSEK]


def calculate_momentum_score(prices_df: pd.DataFrame, price_pivot: pd.DataFrame = None) -> pd.Series:
    """
    Sammansatt Momentum: average of 3m, 6m, 12m price returns.
    
    Uses calendar months (not trading days) per Börslabbet methodology.
    """
    from dateutil.relativedelta import relativedelta
    
    if price_pivot is None:
        if prices_df is None or prices_df.empty:
            return pd.Series(dtype=float)
        
        from services.memory_optimizer import MemoryOptimizer
        prices_df = MemoryOptimizer.optimize_dtypes(prices_df)
        
        if len(prices_df) > 100000:
            logger.info("Large price dataset - using memory-optimized pivot")
            prices_df = prices_df.sort_values('date').tail(50000)
            
        price_pivot = prices_df.pivot_table(index='date', columns='ticker', values='close', aggfunc='last', observed=True).sort_index()
        
        import gc
        del prices_df
        gc.collect()
    
    if price_pivot.empty:
        return pd.Series(dtype=float)
    
    # Ensure index is datetime
    if not isinstance(price_pivot.index, pd.DatetimeIndex):
        price_pivot.index = pd.to_datetime(price_pivot.index)
    
    latest_date = price_pivot.index[-1]
    latest = price_pivot.iloc[-1]
    scores = pd.DataFrame(index=latest.index)
    
    # Use calendar months instead of trading days
    for months in [3, 6, 12]:
        target_date = latest_date - relativedelta(months=months)
        # Find closest trading day on or before target date
        valid_dates = price_pivot.index[price_pivot.index <= target_date]
        if len(valid_dates) > 0:
            past_date = valid_dates[-1]
            past = price_pivot.loc[past_date].replace(0, np.nan)
            scores[f'm{months}'] = (latest / past) - 1
        else:
            scores[f'm{months}'] = np.nan
    
    result = scores.mean(axis=1)
    result = result.replace([np.inf, -np.inf], np.nan)
    return result.dropna()


def calculate_piotroski_f_score(fund_df: pd.DataFrame, prev_fund_df: pd.DataFrame = None) -> pd.Series:
    """
    Full Piotroski F-Score (0-9 scale).
    
    Profitability (4 points):
    1. ROA > 0
    2. Operating Cash Flow > 0
    3. ROA improving (vs prior year)
    4. Cash Flow > Net Income (accruals)
    
    Leverage/Liquidity (3 points):
    5. Long-term debt ratio decreasing
    6. Current ratio improving
    7. No new shares issued (dilution)
    
    Operating Efficiency (2 points):
    8. Gross margin improving
    9. Asset turnover improving
    """
    if fund_df.empty:
        return pd.Series(dtype=float)
    
    df = fund_df.set_index('ticker')
    score = pd.Series(0, index=df.index)
    
    # === Profitability (4 points) ===
    # 1. Positive ROA
    if 'roa' in df.columns:
        score += (df['roa'].fillna(0) > 0).astype(int)
    
    # 2. Positive Operating Cash Flow
    if 'operating_cf' in df.columns:
        score += (df['operating_cf'].fillna(0) > 0).astype(int)
    elif 'fcfroe' in df.columns:
        score += (df['fcfroe'].fillna(0) > 0).astype(int)
    
    # 3. ROA improving (compare to prior year if available)
    if prev_fund_df is not None and 'roa' in df.columns:
        prev = prev_fund_df.set_index('ticker')
        if 'roa' in prev.columns:
            common = df.index.intersection(prev.index)
            improving = df.loc[common, 'roa'] > prev.loc[common, 'roa']
            score.loc[common] += improving.astype(int)
    elif 'roa' in df.columns:
        score += (df['roa'].fillna(0) > df['roa'].median()).astype(int)
    
    # 4. Cash Flow > Net Income (quality of earnings)
    if 'operating_cf' in df.columns and 'net_income' in df.columns:
        score += (df['operating_cf'].fillna(0) > df['net_income'].fillna(0)).astype(int)
    elif 'fcfroe' in df.columns and 'roe' in df.columns:
        score += (df['fcfroe'].fillna(0) > df['roe'].fillna(0)).astype(int)
    
    # === Leverage/Liquidity (3 points) ===
    # 5. Long-term debt ratio decreasing
    if prev_fund_df is not None and 'long_term_debt' in df.columns and 'total_assets' in df.columns:
        prev = prev_fund_df.set_index('ticker')
        if 'long_term_debt' in prev.columns and 'total_assets' in prev.columns:
            curr_ratio = df['long_term_debt'] / df['total_assets'].replace(0, np.nan)
            prev_ratio = prev['long_term_debt'] / prev['total_assets'].replace(0, np.nan)
            common = df.index.intersection(prev.index)
            decreasing = curr_ratio.loc[common] < prev_ratio.loc[common]
            score.loc[common] += decreasing.fillna(False).astype(int)
    else:
        score += 1  # Give benefit of doubt if no data
    
    # 6. Current ratio improving
    if prev_fund_df is not None and 'current_ratio' in df.columns:
        prev = prev_fund_df.set_index('ticker')
        if 'current_ratio' in prev.columns:
            common = df.index.intersection(prev.index)
            improving = df.loc[common, 'current_ratio'] > prev.loc[common, 'current_ratio']
            score.loc[common] += improving.fillna(False).astype(int)
    elif 'current_ratio' in df.columns:
        score += (df['current_ratio'].fillna(0) > 1).astype(int)
    
    # 7. No dilution (shares outstanding not increased)
    if prev_fund_df is not None and 'shares_outstanding' in df.columns:
        prev = prev_fund_df.set_index('ticker')
        if 'shares_outstanding' in prev.columns:
            common = df.index.intersection(prev.index)
            no_dilution = df.loc[common, 'shares_outstanding'] <= prev.loc[common, 'shares_outstanding']
            score.loc[common] += no_dilution.fillna(True).astype(int)
    else:
        score += 1
    
    # === Operating Efficiency (2 points) ===
    # 8. Gross margin improving
    if prev_fund_df is not None and 'gross_margin' in df.columns:
        prev = prev_fund_df.set_index('ticker')
        if 'gross_margin' in prev.columns:
            common = df.index.intersection(prev.index)
            improving = df.loc[common, 'gross_margin'] > prev.loc[common, 'gross_margin']
            score.loc[common] += improving.fillna(False).astype(int)
    elif 'gross_margin' in df.columns:
        score += (df['gross_margin'].fillna(0) > df['gross_margin'].median()).astype(int)
    
    # 9. Asset turnover improving
    if prev_fund_df is not None and 'asset_turnover' in df.columns:
        prev = prev_fund_df.set_index('ticker')
        if 'asset_turnover' in prev.columns:
            common = df.index.intersection(prev.index)
            improving = df.loc[common, 'asset_turnover'] > prev.loc[common, 'asset_turnover']
            score.loc[common] += improving.fillna(False).astype(int)
    elif 'asset_turnover' in df.columns:
        score += (df['asset_turnover'].fillna(0) > df['asset_turnover'].median()).astype(int)
    
    return score


def apply_banding(current_holdings: list, new_rankings: pd.DataFrame, top_pct: float = 10, sell_threshold_pct: float = 20) -> pd.DataFrame:
    """
    Apply banding logic for momentum rebalancing.
    Only sell if stock drops out of top sell_threshold_pct%.
    
    Args:
        current_holdings: List of currently held tickers
        new_rankings: DataFrame with ticker, rank, score
        top_pct: Top percentage to buy new stocks from (default 10%)
        sell_threshold_pct: Only sell if stock drops below this percentile (default 20%)
    """
    if new_rankings.empty:
        return new_rankings
    
    total_stocks = len(new_rankings)
    top_n = max(1, int(total_stocks * top_pct / 100))
    sell_threshold = max(1, int(total_stocks * sell_threshold_pct / 100))
    
    # Keep current holdings if still in top sell_threshold_pct
    keep = []
    for ticker in current_holdings:
        if ticker in new_rankings['ticker'].values:
            rank = new_rankings[new_rankings['ticker'] == ticker]['rank'].iloc[0]
            if rank <= sell_threshold:
                keep.append(ticker)
    
    # Fill remaining slots from top_n
    slots_available = 10 - len(keep)
    new_buys = new_rankings[~new_rankings['ticker'].isin(keep)].head(slots_available)
    
    # Combine
    keep_df = new_rankings[new_rankings['ticker'].isin(keep)]
    result = pd.concat([keep_df, new_buys]).head(10)
    result['rank'] = range(1, len(result) + 1)
    
    return result


def _filter_top_percentile(scores: pd.Series, percentile: float = 10) -> pd.Index:
    """Keep top N% of stocks by score."""
    n = max(1, int(len(scores) * percentile / 100))
    return scores.nlargest(n).index


def calculate_momentum_with_quality_filter(
    prices_df: pd.DataFrame, 
    fund_df: pd.DataFrame,
    prev_fund_df: pd.DataFrame = None,
    current_holdings: list = None,
    full_universe: bool = False
) -> pd.DataFrame:
    """
    Sammansatt Momentum strategy with Piotroski F-Score filter.
    
    Börslabbet methodology:
    - Composite momentum = average(3m, 6m, 12m returns)
    - Filter: Piotroski F-Score >= 5
    - Excludes financial companies (but NOT Investmentbolag)
    - Excludes Norwegian stocks
    """
    # Market cap filter + exclude financials (for_momentum=True keeps Investmentbolag)
    filtered_fund = filter_by_market_cap(fund_df)
    filtered_fund = filter_financial_companies(filtered_fund, for_momentum=True)
    filtered_fund = filter_norwegian_stocks(filtered_fund)
    valid_tickers = set(filtered_fund['ticker'].values) if not filtered_fund.empty else None
    
    # Filter prices to valid tickers
    if valid_tickers:
        prices_filtered = prices_df[prices_df['ticker'].isin(valid_tickers)]
    else:
        prices_filtered = prices_df
    
    momentum = calculate_momentum_score(prices_filtered)
    f_scores = calculate_piotroski_f_score(filtered_fund, prev_fund_df)
    
    # Remove stocks with F-Score < 5 (Börslabbet uses F-Score >= 5)
    if not f_scores.empty:
        valid = f_scores[f_scores >= 5].index
        filtered = momentum[momentum.index.isin(valid)]
    else:
        filtered = momentum
    
    if filtered.empty:
        filtered = momentum
    
    # Create rankings
    ranked = filtered.sort_values(ascending=False)
    rankings = pd.DataFrame({
        'ticker': ranked.index,
        'rank': range(1, len(ranked) + 1),
        'score': ranked.values
    })
    
    # Apply banding if current holdings provided
    if current_holdings:
        rankings = apply_banding(current_holdings, rankings)
    elif not full_universe:
        rankings = rankings.head(10)
    
    return rankings


def calculate_value_score(fund_df: pd.DataFrame, prices_df: pd.DataFrame = None, price_pivot: pd.DataFrame = None) -> pd.DataFrame:
    """
    Trendande Värde: Top value stocks sorted by 6m momentum.
    
    Methodology:
    - Sammansatt Värde = composite rank of P/E, P/B, P/S, P/FCF, EV/EBITDA, Div Yield
    - Filter to top 40% by value score
    - Sort by 6m momentum
    - Excludes financial companies and Norwegian stocks
    """
    if fund_df.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Market cap filter + exclude financials + exclude Norwegian stocks
    filtered = filter_by_market_cap(fund_df)
    filtered = filter_financial_companies(filtered)
    filtered = filter_norwegian_stocks(filtered)
    if filtered.empty:
        filtered = fund_df
    
    df = filtered.set_index('ticker')
    ranks = pd.DataFrame(index=df.index)
    
    # Lower = better for valuation metrics
    for col in ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda']:
        if col in df.columns:
            ranks[col] = df[col].rank(ascending=True, na_option='bottom')
    
    # Higher = better for dividend yield
    if 'dividend_yield' in df.columns:
        ranks['dividend_yield'] = df['dividend_yield'].rank(ascending=False, na_option='bottom')
    
    if ranks.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Average ranks to get composite value score
    value_score = ranks.mean(axis=1, skipna=True)
    
    # Top 40% by value score (lowest = best value)
    n_top = max(1, int(len(value_score) * 0.4))
    top_value = value_score.nsmallest(n_top).index
    
    if price_pivot is None and (prices_df is None or prices_df.empty):
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Sort by 6m momentum
    mom_6m = calculate_6m_momentum(prices_df, price_pivot=price_pivot)
    filtered_mom = mom_6m[mom_6m.index.isin(top_value)]
    if filtered_mom.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    top_n = filtered_mom.sort_values(ascending=False)
    top10 = top_n.head(10)
    return pd.DataFrame({'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values})


def calculate_6m_momentum(prices_df: pd.DataFrame, price_pivot: pd.DataFrame = None) -> pd.Series:
    """Calculate 6-month momentum only (for Trendande strategies)."""
    from dateutil.relativedelta import relativedelta
    
    if price_pivot is None:
        if prices_df is None or prices_df.empty:
            return pd.Series(dtype=float)
        price_pivot = prices_df.pivot_table(index='date', columns='ticker', values='close', aggfunc='last', observed=True).sort_index()
    
    if price_pivot.empty:
        return pd.Series(dtype=float)
    
    if not isinstance(price_pivot.index, pd.DatetimeIndex):
        price_pivot.index = pd.to_datetime(price_pivot.index)
    
    latest_date = price_pivot.index[-1]
    latest = price_pivot.iloc[-1]
    
    target_date = latest_date - relativedelta(months=6)
    valid_dates = price_pivot.index[price_pivot.index <= target_date]
    if len(valid_dates) == 0:
        return pd.Series(dtype=float)
    
    past_date = valid_dates[-1]
    past = price_pivot.loc[past_date].replace(0, np.nan)
    result = (latest / past) - 1
    return result.replace([np.inf, -np.inf], np.nan).dropna()


def calculate_dividend_score(fund_df: pd.DataFrame, prices_df: pd.DataFrame = None, price_pivot: pd.DataFrame = None) -> pd.DataFrame:
    """
    Trendande Utdelning: Top dividend stocks sorted by 6m momentum.
    
    Methodology:
    - Filter to top 40% by dividend yield
    - Sort by 6m momentum
    - Excludes financial companies and Norwegian stocks
    """
    if fund_df.empty or 'dividend_yield' not in fund_df.columns:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Market cap filter + exclude financials + exclude Norwegian stocks
    filtered = filter_by_market_cap(fund_df)
    filtered = filter_financial_companies(filtered)
    filtered = filter_norwegian_stocks(filtered)
    if filtered.empty:
        filtered = fund_df
    
    df = filtered.set_index('ticker')
    
    # Filter to top 40% by dividend yield
    n_top = max(1, int(len(df) * 0.4))
    top_dividend = df.nlargest(n_top, 'dividend_yield').index
    
    if price_pivot is None and (prices_df is None or prices_df.empty):
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Sort by 6m momentum
    mom_6m = calculate_6m_momentum(prices_df, price_pivot=price_pivot)
    filtered_mom = mom_6m[mom_6m.index.isin(top_dividend)]
    if filtered_mom.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    top_n = filtered_mom.sort_values(ascending=False)
    top10 = top_n.head(10)
    return pd.DataFrame({'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values})


def calculate_quality_score(fund_df: pd.DataFrame, prices_df: pd.DataFrame = None, price_pivot: pd.DataFrame = None) -> pd.DataFrame:
    """
    Trendande Kvalitet: Top quality stocks sorted by 6m momentum.
    
    Methodology:
    - Sammansatt ROI = composite rank of ROE, ROA, ROIC, FCFROE
    - Filter to top 40% by quality score
    - Sort by 6m momentum
    - Excludes financial companies and Norwegian stocks
    """
    if fund_df.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Market cap filter + exclude financials + exclude Norwegian stocks
    filtered = filter_by_market_cap(fund_df)
    filtered = filter_financial_companies(filtered)
    filtered = filter_norwegian_stocks(filtered)
    if filtered.empty:
        filtered = fund_df
    
    df = filtered.set_index('ticker')
    quality_cols = ['roe', 'roa', 'roic', 'fcfroe']
    
    ranks = pd.DataFrame(index=df.index)
    for col in quality_cols:
        if col in df.columns:
            ranks[col] = df[col].rank(ascending=False, na_option='bottom')
    
    if ranks.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Average ranks to get composite quality score (lower = better)
    quality_score = ranks.mean(axis=1)
    
    # Top 40% by quality score (lowest = best quality)
    n_top = max(1, int(len(quality_score) * 0.4))
    top_quality = quality_score.nsmallest(n_top).index
    
    if price_pivot is None and (prices_df is None or prices_df.empty):
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Sort by 6m momentum
    mom_6m = calculate_6m_momentum(prices_df, price_pivot=price_pivot)
    filtered_mom = mom_6m[mom_6m.index.isin(top_quality)]
    if filtered_mom.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    top_n = filtered_mom.sort_values(ascending=False)
    top10 = top_n.head(10)
    return pd.DataFrame({'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values})


def rank_and_select_top_n(scores: pd.Series, config: dict, n: int = 10) -> pd.DataFrame:
    """Rank stocks by score and select top N."""
    if scores.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    n = config.get('position_count', n)
    top = scores.sort_values(ascending=False).head(n)
    return pd.DataFrame({'ticker': top.index, 'rank': range(1, len(top)+1), 'score': top.values})


def calculate_momentum_score_from_tv(fund_df: pd.DataFrame) -> pd.Series:
    """
    Calculate Sammansatt Momentum from TradingView's pre-calculated returns.
    TradingView provides Perf.3M, Perf.6M, Perf.Y directly.
    """
    if fund_df.empty:
        return pd.Series(dtype=float)
    
    df = fund_df.set_index('ticker')
    momentum = (
        df['perf_3m'].fillna(0) + 
        df['perf_6m'].fillna(0) + 
        df['perf_12m'].fillna(0)
    ) / 3
    return momentum.replace([np.inf, -np.inf], np.nan).dropna()


def get_fscore_from_tv(fund_df: pd.DataFrame) -> pd.Series:
    """Get F-Score from TradingView data (already pre-calculated)."""
    if fund_df.empty or 'piotroski_f_score' not in fund_df.columns:
        return pd.Series(dtype=float)
    return fund_df.set_index('ticker')['piotroski_f_score']
