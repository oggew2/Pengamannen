#!/usr/bin/env python3
"""
Test different Nordic momentum algorithm variants to find closest match to Börslabbet.

This script tests various parameter combinations without modifying production code.
"""
import sys
sys.path.insert(0, '/Users/ewreosk/Kiro/borslabbet-app/backend')

from services.tradingview_fetcher import TradingViewFetcher
import pandas as pd

# Börslabbet reference data (Jan 30, 2026)
BORSLABBET_TOP40 = [
    "BITTI", "GOMX", "SANION", "NELLY", "LUMI", "PAMPALO", "OVZON", "LUG", "SAAB B", "SVIK",
    "VWS", "NREST", "HSHP", "WRT1V", "XANO B", "MTHH", "KIT", "B2I", "PAAL B", "ASPO",
    "ANORA", "KCR", "SAND", "NKT", "ISS", "ATT", "WWIB", "ACR", "NOL", "CLA B",
    "BWO", "NHY", "HANZA", "BIOA B", "SMOP", "PEXIP", "OET", "NLFSK", "GMAB", "FLS"
]

# Börslabbet F-Scores for reference (from their data)
BORSLABBET_FSCORES = {
    "BITTI": 5, "GOMX": 5, "SANION": 5, "NELLY": 5, "LUMI": 7, "PAMPALO": 8,
    "OVZON": 7, "LUG": 5, "SAAB B": 6, "SVIK": 8, "VWS": 6, "NREST": 5,
    "HSHP": 6, "WRT1V": 8, "XANO B": 9, "MTHH": 8, "KIT": 5, "B2I": 5,
    "PAAL B": 5, "ASPO": 6, "ANORA": 7, "KCR": 6, "SAND": 8, "NKT": 6,
    "ISS": 6, "ATT": 8, "WWIB": 7, "ACR": 7, "NOL": 5, "CLA B": 7,
    "BWO": 6, "NHY": 8, "HANZA": 6, "BIOA B": 7, "SMOP": 6, "PEXIP": 7,
    "OET": 6, "NLFSK": 5, "GMAB": 7, "FLS": 7
}

def normalize_ticker(t):
    """Normalize ticker for comparison."""
    return t.upper().replace(" ", "_").replace("-", "_")

def compute_rankings(df, f_score_threshold=5, exclude_finance=True, filter_capital_companies=True):
    """Compute momentum rankings with given parameters."""
    result = df.copy()
    
    # Finance filter
    if exclude_finance:
        result = result[result['sector'] != 'Finance']
    
    # Preference shares filter
    result = result[~result['ticker'].str.contains('PREF', case=False, na=False)]
    
    # Investment company filter
    def is_investment_company(name):
        name_lower = name.lower()
        if 'investment ab' in name_lower or 'investment a/s' in name_lower:
            return True
        if 'invest ab' in name_lower:
            return True
        if name_lower.endswith('capital ab') or name_lower.endswith('capital a/s'):
            return True
        # Additional filter for "Capital" companies
        if filter_capital_companies and ' capital ' in name_lower:
            return True
        return False
    
    result = result[~result['name'].apply(is_investment_company)]
    
    # Calculate momentum
    result['momentum'] = (
        result['perf_3m'].fillna(0) + 
        result['perf_6m'].fillna(0) + 
        result['perf_12m'].fillna(0)
    ) / 3
    
    # F-Score filter
    if f_score_threshold > 0:
        result = result[result['piotroski_f_score'].fillna(0) >= f_score_threshold]
    
    # Rank by momentum
    result = result.sort_values('momentum', ascending=False)
    
    return result.head(40)

def compare_to_borslabbet(our_rankings):
    """Compare our rankings to Börslabbet and return match statistics."""
    our_tickers = set(normalize_ticker(t) for t in our_rankings['ticker'].values)
    bl_tickers = set(normalize_ticker(t) for t in BORSLABBET_TOP40)
    
    matches = our_tickers & bl_tickers
    our_only = our_tickers - bl_tickers
    bl_only = bl_tickers - our_tickers
    
    # Top 10 match
    our_top10 = set(normalize_ticker(t) for t in our_rankings['ticker'].head(10).values)
    bl_top10 = set(normalize_ticker(t) for t in BORSLABBET_TOP40[:10])
    top10_matches = len(our_top10 & bl_top10)
    
    return {
        'total_matches': len(matches),
        'top10_matches': top10_matches,
        'our_only': our_only,
        'bl_only': bl_only
    }

def main():
    print("Fetching Nordic stocks from TradingView...")
    fetcher = TradingViewFetcher()
    stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
    df = pd.DataFrame(stocks)
    print(f"Fetched {len(df)} stocks\n")
    
    # Test different F-Score thresholds
    print("=" * 80)
    print("TESTING DIFFERENT F-SCORE THRESHOLDS")
    print("=" * 80)
    
    for threshold in [0, 3, 4, 5, 6]:
        rankings = compute_rankings(df, f_score_threshold=threshold)
        stats = compare_to_borslabbet(rankings)
        print(f"\nF-Score >= {threshold}:")
        print(f"  Top 40 matches: {stats['total_matches']}/40")
        print(f"  Top 10 matches: {stats['top10_matches']}/10")
        if stats['bl_only']:
            print(f"  Missing from us: {sorted(stats['bl_only'])}")
        if stats['our_only']:
            print(f"  Extra in ours: {sorted(stats['our_only'])}")
    
    # Test with capital company filter
    print("\n" + "=" * 80)
    print("TESTING WITH CAPITAL COMPANY FILTER (F-Score >= 5)")
    print("=" * 80)
    
    rankings = compute_rankings(df, f_score_threshold=5, filter_capital_companies=True)
    stats = compare_to_borslabbet(rankings)
    print(f"\nWith 'Capital' company filter:")
    print(f"  Top 40 matches: {stats['total_matches']}/40")
    print(f"  Top 10 matches: {stats['top10_matches']}/10")
    if stats['bl_only']:
        print(f"  Missing from us: {sorted(stats['bl_only'])}")
    if stats['our_only']:
        print(f"  Extra in ours: {sorted(stats['our_only'])}")
    
    # F-Score comparison
    print("\n" + "=" * 80)
    print("F-SCORE COMPARISON: OUR DATA vs BÖRSLABBET")
    print("=" * 80)
    
    print("\nStocks where F-Score differs significantly:")
    for ticker in BORSLABBET_TOP40:
        norm = normalize_ticker(ticker)
        our_row = df[df['ticker'].apply(normalize_ticker) == norm]
        if not our_row.empty:
            our_f = our_row.iloc[0].get('piotroski_f_score', 0) or 0
            bl_f = BORSLABBET_FSCORES.get(ticker, 0)
            if abs(our_f - bl_f) >= 2:
                print(f"  {ticker:12} Our F={our_f} vs BL F={bl_f} (diff={our_f - bl_f:+d})")
    
    # Best match analysis
    print("\n" + "=" * 80)
    print("DETAILED ANALYSIS WITH F-SCORE >= 5 + CAPITAL FILTER")
    print("=" * 80)
    
    rankings = compute_rankings(df, f_score_threshold=5, filter_capital_companies=True)
    print("\nOur Top 40:")
    for i, (_, row) in enumerate(rankings.iterrows(), 1):
        ticker_norm = normalize_ticker(row['ticker'])
        in_bl = "✓" if ticker_norm in [normalize_ticker(t) for t in BORSLABBET_TOP40] else "✗"
        print(f"{i:2}. {row['ticker']:12} Mom={row['momentum']:6.1f}% F={row.get('piotroski_f_score', 'N/A'):>3} {in_bl}")

if __name__ == "__main__":
    main()
