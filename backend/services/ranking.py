"""
Ranking service - strategy scoring functions for Börslabbet strategies.
Based on strategies.yaml configuration.

Börslabbet Strategy Rules (Verified 2024-2025):
- Sammansatt Momentum: Quarterly, momentum 3/6/12m, F-Score >= 4
- Trendande Värde: Annual (Jan), P/E + P/B + P/S + EV/EBITDA (lower = better)
- Trendande Utdelning: Annual (Feb), dividend yield, filters for sustainability
- Trendande Kvalitet: Annual (Mar), ROIC + momentum, quality filters
"""
import pandas as pd
import numpy as np
from scipy import stats


def calculate_momentum_score(
    prices_df: pd.DataFrame,
    periods: list[int] = [3, 6, 12],
    weights: list[float] = [0.33, 0.33, 0.34]
) -> pd.Series:
    """
    Calculate composite momentum score per Börslabbet rules.
    
    Weights: 3m (33%), 6m (33%), 12m (34%)
    Normalization: z-score
    """
    if prices_df.empty:
        return pd.Series(dtype=float)
    
    latest = prices_df.groupby('ticker')['date'].max()
    momentum_scores = pd.DataFrame(index=latest.index)
    
    for period in periods:
        days = period * 21  # Trading days per month
        returns = []
        for ticker in latest.index:
            ticker_prices = prices_df[prices_df['ticker'] == ticker].sort_values('date')
            if len(ticker_prices) >= days:
                current = ticker_prices['close'].iloc[-1]
                past = ticker_prices['close'].iloc[-days]
                returns.append((current - past) / past if past != 0 else 0)
            else:
                returns.append(np.nan)
        momentum_scores[f'mom_{period}m'] = returns
    
    # Z-score normalize each period
    for col in momentum_scores.columns:
        valid = momentum_scores[col].dropna()
        if len(valid) > 1:
            momentum_scores[col] = (momentum_scores[col] - valid.mean()) / valid.std()
    
    # Weighted average
    composite = sum(
        momentum_scores.iloc[:, i].fillna(0) * weights[i] 
        for i in range(min(len(periods), len(weights)))
    )
    
    return composite


def calculate_piotroski_f_score(fundamentals_df: pd.DataFrame) -> pd.Series:
    """
    Calculate Piotroski F-Score (simplified 0-4 scale for available data).
    
    Original F-Score is 0-9, we use 4 criteria:
    1. Positive ROA (profitability)
    2. Positive operating cash flow (FCF > 0)
    3. ROA above median (improving)
    4. Cash flow > Net Income (quality of earnings: fcfroe > roe)
    
    Börslabbet requires F-Score >= 4 (original scale), 
    which maps to >= 2 on our 0-4 scale.
    """
    if fundamentals_df.empty:
        return pd.Series(dtype=float)
    
    df = fundamentals_df.set_index('ticker')
    score = pd.Series(0, index=df.index)
    
    # 1. Positive ROA
    if 'roa' in df.columns:
        score += (df['roa'].fillna(0) > 0).astype(int)
    
    # 2. Positive FCF (approximated by fcfroe)
    if 'fcfroe' in df.columns:
        score += (df['fcfroe'].fillna(0) > 0).astype(int)
    
    # 3. ROA above median (improving profitability proxy)
    if 'roa' in df.columns:
        score += (df['roa'].fillna(0) > df['roa'].median()).astype(int)
    
    # 4. Quality of earnings: cash flow > accruals
    if 'fcfroe' in df.columns and 'roe' in df.columns:
        score += (df['fcfroe'].fillna(0) > df['roe'].fillna(0)).astype(int)
    
    return score


def calculate_momentum_with_quality_filter(
    prices_df: pd.DataFrame,
    fundamentals_df: pd.DataFrame,
    min_f_score: int = 2
) -> pd.DataFrame:
    """
    Sammansatt Momentum strategy with Piotroski F-Score filter.
    
    Börslabbet rules:
    - Composite momentum (3m, 6m, 12m equally weighted)
    - Filter: F-Score >= 4 (original) = >= 2 (our simplified scale)
    - Select top 10
    - Rebalance quarterly
    """
    momentum = calculate_momentum_score(prices_df)
    f_scores = calculate_piotroski_f_score(fundamentals_df)
    
    # Filter by F-Score
    valid_tickers = f_scores[f_scores >= min_f_score].index
    filtered_momentum = momentum[momentum.index.isin(valid_tickers)]
    
    if filtered_momentum.empty:
        # Fallback: return top momentum without filter if no stocks pass
        filtered_momentum = momentum
    
    # Rank and return top 10
    ranked = filtered_momentum.sort_values(ascending=False).head(10)
    return pd.DataFrame({
        'ticker': ranked.index,
        'rank': range(1, len(ranked) + 1),
        'score': ranked.values
    })


def calculate_value_score(fundamentals_df: pd.DataFrame) -> pd.Series:
    """
    Trendande Värde strategy - cheapest stocks by multiples.
    
    Börslabbet rules:
    - Metrics: P/E, P/B, P/S, EV/EBITDA (equal weight 25% each)
    - Lower multiple = better (inverse ranking)
    - Z-score normalization
    - Select top 10
    - Rebalance annually (January)
    """
    if fundamentals_df.empty:
        return pd.Series(dtype=float)
    
    # Per Börslabbet: only these 4 metrics
    metrics = ['pe', 'pb', 'ps', 'ev_ebitda']
    df = fundamentals_df.set_index('ticker')
    
    scores = pd.DataFrame(index=df.index)
    for metric in metrics:
        if metric in df.columns:
            valid = df[metric].dropna()
            if len(valid) > 1:
                # Invert: lower valuation = higher score
                z = (df[metric].fillna(valid.median()) - valid.mean()) / valid.std()
                scores[metric] = -z  # Negative because lower is better
    
    if scores.empty:
        return pd.Series(dtype=float)
    
    # Equal weight average
    return scores.mean(axis=1)


def calculate_dividend_score(fundamentals_df: pd.DataFrame) -> pd.Series:
    """
    Trendande Utdelning strategy - high sustainable dividends.
    
    Börslabbet rules:
    - Primary metric: dividend_yield (higher = better)
    - CRITICAL FILTERS:
      * payout_ratio < 100% (sustainable)
      * ROE > 5% (profitable)
      * dividend_yield > 1.5% (meaningful)
    - Select top 10
    - Rebalance annually (February)
    """
    if fundamentals_df.empty:
        return pd.Series(dtype=float)
    
    df = fundamentals_df.set_index('ticker').copy()
    
    if 'dividend_yield' not in df.columns:
        return pd.Series(dtype=float)
    
    # Apply sustainability filters
    mask = pd.Series(True, index=df.index)
    
    # Filter 1: Payout ratio < 100%
    if 'payout_ratio' in df.columns:
        mask &= (df['payout_ratio'].fillna(0) < 1.0)
    
    # Filter 2: ROE > 5%
    if 'roe' in df.columns:
        mask &= (df['roe'].fillna(0) > 0.05)
    
    # Filter 3: Dividend yield > 1.5%
    mask &= (df['dividend_yield'].fillna(0) > 0.015)
    
    filtered = df[mask]
    if filtered.empty:
        return pd.Series(dtype=float)
    
    # Rank by dividend yield (higher = better)
    return filtered['dividend_yield']


def calculate_quality_score(fundamentals_df: pd.DataFrame, prices_df: pd.DataFrame = None) -> pd.Series:
    """
    Trendande Kvalitet strategy - profitable growth stocks.
    
    Börslabbet rules:
    - Primary: ROIC (50% weight), fallback to ROE
    - Secondary: Momentum composite (50% weight)
    - FILTERS:
      * ROIC > 10% OR ROE > 15%
    - Select top 10
    - Rebalance annually (March)
    """
    if fundamentals_df.empty:
        return pd.Series(dtype=float)
    
    df = fundamentals_df.set_index('ticker').copy()
    
    # Quality filter: ROIC > 10% OR ROE > 15%
    mask = pd.Series(False, index=df.index)
    if 'roic' in df.columns:
        mask |= (df['roic'].fillna(0) > 0.10)
    if 'roe' in df.columns:
        mask |= (df['roe'].fillna(0) > 0.15)
    
    filtered = df[mask]
    if filtered.empty:
        return pd.Series(dtype=float)
    
    # Primary score: ROIC (or ROE as fallback)
    if 'roic' in filtered.columns and filtered['roic'].notna().any():
        valid = filtered['roic'].dropna()
        if len(valid) > 1:
            quality_score = (filtered['roic'].fillna(valid.median()) - valid.mean()) / valid.std()
        else:
            quality_score = pd.Series(0.0, index=filtered.index)
    elif 'roe' in filtered.columns:
        valid = filtered['roe'].dropna()
        if len(valid) > 1:
            quality_score = (filtered['roe'].fillna(valid.median()) - valid.mean()) / valid.std()
        else:
            quality_score = pd.Series(0.0, index=filtered.index)
    else:
        quality_score = pd.Series(0.0, index=filtered.index)
    
    # Combine with momentum (50/50) if prices available
    if prices_df is not None and not prices_df.empty:
        momentum = calculate_momentum_score(prices_df)
        common = quality_score.index.intersection(momentum.index)
        if len(common) > 0:
            # Normalize momentum to same scale
            mom_subset = momentum.loc[common]
            if mom_subset.std() > 0:
                mom_normalized = (mom_subset - mom_subset.mean()) / mom_subset.std()
            else:
                mom_normalized = mom_subset
            
            # 50% ROIC + 50% Momentum
            quality_score.loc[common] = quality_score.loc[common] * 0.5 + mom_normalized * 0.5
    
    return quality_score


def rank_and_select_top_n(scores: pd.Series, config: dict, n: int = 10) -> pd.DataFrame:
    """
    Rank stocks by score and select top N.
    
    Args:
        scores: Series indexed by ticker with composite scores
        config: Strategy config (reads 'position_count' or 'portfolio_size')
        n: Fallback if not in config
    """
    if scores.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Support both old and new config key names
    n = config.get('position_count', config.get('portfolio_size', n))
    
    sorted_scores = scores.sort_values(ascending=False)
    top_n = sorted_scores.head(n)
    
    return pd.DataFrame({
        'ticker': top_n.index,
        'rank': range(1, len(top_n) + 1),
        'score': top_n.values
    })
