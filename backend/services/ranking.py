"""
Ranking service - Börslabbet strategy scoring functions.

Verified Strategy Rules (from börslabbet.se/borslabbets-strategier):
- Universe: Top 40% by market cap (for liquidity)
- Piotroski F-Score: 0-9 scale quality filter
- All strategies use percentile-based filtering
"""
import pandas as pd
import numpy as np


def filter_by_market_cap(fund_df: pd.DataFrame, percentile: float = 40) -> pd.DataFrame:
    """
    Filter to top N% of stocks by market cap.
    Börslabbet uses top 40% for liquidity.
    """
    if fund_df.empty or 'market_cap' not in fund_df.columns:
        return fund_df
    
    threshold = fund_df['market_cap'].quantile(1 - percentile / 100)
    return fund_df[fund_df['market_cap'] >= threshold]


def calculate_momentum_score(prices_df: pd.DataFrame) -> pd.Series:
    """Sammansatt Momentum: average of 3m, 6m, 12m price returns."""
    if prices_df.empty:
        return pd.Series(dtype=float)
    
    latest = prices_df.groupby('ticker')['date'].max()
    scores = pd.DataFrame(index=latest.index)
    
    for period in [3, 6, 12]:
        days = period * 21
        returns = []
        for ticker in latest.index:
            tp = prices_df[prices_df['ticker'] == ticker].sort_values('date')
            if len(tp) >= days:
                returns.append(tp['close'].iloc[-1] / tp['close'].iloc[-days] - 1)
            else:
                returns.append(np.nan)
        scores[f'm{period}'] = returns
    
    return scores.mean(axis=1)


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
    current_holdings: list = None
) -> pd.DataFrame:
    """
    Sammansatt Momentum strategy with full Piotroski filter.
    
    Step 1: Filter to top 40% by market cap
    Step 2: Calculate momentum (avg 3m, 6m, 12m)
    Step 3: Remove stocks with F-Score <= 3 (bottom quality)
    Step 4: Apply banding if current holdings provided
    Step 5: Select top 10 by momentum
    """
    # Market cap filter
    filtered_fund = filter_by_market_cap(fund_df, 40)
    valid_tickers = set(filtered_fund['ticker'].values) if not filtered_fund.empty else None
    
    # Filter prices to valid tickers
    if valid_tickers:
        prices_filtered = prices_df[prices_df['ticker'].isin(valid_tickers)]
    else:
        prices_filtered = prices_df
    
    momentum = calculate_momentum_score(prices_filtered)
    f_scores = calculate_piotroski_f_score(filtered_fund, prev_fund_df)
    
    # Remove stocks with F-Score <= 3 (out of 9)
    if not f_scores.empty:
        valid = f_scores[f_scores > 3].index
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
    else:
        rankings = rankings.head(10)
    
    return rankings


def calculate_value_score(fund_df: pd.DataFrame, prices_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Trendande Värde: 6-factor Sammansatt Värde.
    Now includes P/FCF metric.
    """
    if fund_df.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Market cap filter
    filtered = filter_by_market_cap(fund_df, 40)
    if filtered.empty:
        filtered = fund_df
    
    df = filtered.set_index('ticker')
    ranks = pd.DataFrame(index=df.index)
    
    # Lower = better
    for col in ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda']:
        if col in df.columns:
            ranks[col] = df[col].rank(ascending=True, na_option='bottom')
    
    # Higher = better
    if 'dividend_yield' in df.columns:
        ranks['dividend_yield'] = df['dividend_yield'].rank(ascending=False, na_option='bottom')
    
    if ranks.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    value_score = ranks.mean(axis=1)
    top_value = _filter_top_percentile(-value_score, 10)
    
    if prices_df is not None and not prices_df.empty:
        momentum = calculate_momentum_score(prices_df)
        filtered_mom = momentum[momentum.index.isin(top_value)]
        top10 = filtered_mom.sort_values(ascending=False).head(10)
    else:
        top10 = value_score[value_score.index.isin(top_value)].nsmallest(10)
    
    return pd.DataFrame({'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values})


def calculate_dividend_score(fund_df: pd.DataFrame, prices_df: pd.DataFrame = None) -> pd.DataFrame:
    """Trendande Utdelning with market cap filter."""
    if fund_df.empty or 'dividend_yield' not in fund_df.columns:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    filtered = filter_by_market_cap(fund_df, 40)
    if filtered.empty:
        filtered = fund_df
    
    df = filtered.set_index('ticker')
    top_yield = _filter_top_percentile(df['dividend_yield'], 10)
    
    if prices_df is not None and not prices_df.empty:
        momentum = calculate_momentum_score(prices_df)
        filtered_mom = momentum[momentum.index.isin(top_yield)]
        top10 = filtered_mom.sort_values(ascending=False).head(10)
    else:
        top10 = df.loc[top_yield, 'dividend_yield'].nlargest(10)
    
    return pd.DataFrame({'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values})


def calculate_quality_score(fund_df: pd.DataFrame, prices_df: pd.DataFrame = None) -> pd.DataFrame:
    """Trendande Kvalitet with market cap filter."""
    if fund_df.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    filtered = filter_by_market_cap(fund_df, 40)
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
    
    quality_score = ranks.mean(axis=1)
    top_quality = _filter_top_percentile(-quality_score, 10)
    
    if prices_df is not None and not prices_df.empty:
        momentum = calculate_momentum_score(prices_df)
        filtered_mom = momentum[momentum.index.isin(top_quality)]
        top10 = filtered_mom.sort_values(ascending=False).head(10)
    else:
        top10 = quality_score[quality_score.index.isin(top_quality)].nsmallest(10)
    
    return pd.DataFrame({'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values})


def rank_and_select_top_n(scores: pd.Series, config: dict, n: int = 10) -> pd.DataFrame:
    """Rank stocks by score and select top N."""
    if scores.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    n = config.get('position_count', n)
    top = scores.sort_values(ascending=False).head(n)
    return pd.DataFrame({'ticker': top.index, 'rank': range(1, len(top)+1), 'score': top.values})
