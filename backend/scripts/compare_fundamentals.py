"""
Compare TradingView fundamentals against Börslabbet CSV data.
Tests different calculation methods and field variants to find best match.
"""
import requests
import csv
import os
from pathlib import Path

CSV_DIR = Path(os.path.expanduser("~/Downloads"))

def load_borslabbet_data():
    """Load and merge all Börslabbet CSV files."""
    stocks = {}
    
    for path, fields in [
        ("Momentum.csv", [('Kursutveck. 3 mån', 'perf_3m'), ('Kursutveck. 6 mån', 'perf_6m'), 
                         ('Kursutveck. 1 år', 'perf_12m'), ('F-score', 'f_score')]),
        ("Trend_kvalitet.csv", [('ROE', 'roe'), ('ROA', 'roa'), ('ROIC', 'roic'), ('FCFROE', 'fcfroe')]),
        ("trendande_varde.csv", [('P/E', 'pe'), ('P/S', 'ps'), ('P/B', 'pb'), 
                                 ('P/FCF', 'p_fcf'), ('EV/EBITDA', 'ev_ebitda'), ('Direktavk.', 'div_yield')]),
    ]:
        csv_path = CSV_DIR / path
        if csv_path.exists():
            with open(csv_path, encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    ticker = row['Ticker']
                    if ticker not in stocks:
                        stocks[ticker] = {'ticker': ticker, 'name': row['Namn']}
                    for csv_col, key in fields:
                        if row.get(csv_col):
                            try:
                                stocks[ticker][key] = float(row[csv_col]) if '.' in row[csv_col] else int(row[csv_col])
                            except: pass
    return stocks

def fetch_tradingview_data():
    """Fetch data from TradingView with multiple field variants."""
    columns = [
        "name", "description", "market_cap_basic",
        "price_earnings_ttm", "price_book_ratio", "price_sales_ratio",
        "price_free_cash_flow_ttm", "enterprise_value_ebitda_ttm",
        "net_income_ttm", "total_equity_fq", "total_assets_fq",
        "return_on_invested_capital", "free_cash_flow_ttm", "dividend_yield_recent",
        "Perf.3M", "Perf.6M", "Perf.Y", "piotroski_f_score_ttm",
        "ebit_ttm", "total_debt_fq", "cash_n_short_term_invest_fq",
        # Alternative fields
        "return_on_equity", "return_on_assets",
        "return_on_capital_employed_fq", "return_on_total_capital_fq",
        "price_book_fq", "dividends_yield_current", "dividends_yield",
    ]
    
    payload = {
        "filter": [{"left": "market_cap_basic", "operation": "greater", "right": 2e9}],
        "markets": ["sweden"],
        "symbols": {"query": {"types": ["stock", "dr"]}},
        "columns": columns,
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 500]
    }
    
    response = requests.post("https://scanner.tradingview.com/sweden/scan", json=payload, timeout=30)
    response.raise_for_status()
    
    results = {}
    for item in response.json().get('data', []):
        values = item.get('d', [])
        if len(values) != len(columns):
            continue
        
        row = dict(zip(columns, values))
        ticker = item.get('s', '').split(':')[-1]
        
        # Manual calculations
        roe_m = (row['net_income_ttm'] / row['total_equity_fq'] * 100) if row.get('net_income_ttm') and row.get('total_equity_fq') else None
        roa_m = (row['net_income_ttm'] / row['total_assets_fq'] * 100) if row.get('net_income_ttm') and row.get('total_assets_fq') else None
        
        roic_m = None
        if row.get('ebit_ttm'):
            ic = (row.get('total_debt_fq') or 0) + (row.get('total_equity_fq') or 0) - (row.get('cash_n_short_term_invest_fq') or 0)
            if ic > 0: roic_m = row['ebit_ttm'] / ic * 100
        
        fcfroe = (row['free_cash_flow_ttm'] / row['total_equity_fq'] * 100) if row.get('free_cash_flow_ttm') and row.get('total_equity_fq') and row['total_equity_fq'] > 0 else None
        
        results[ticker] = {
            'roe_manual': roe_m, 'roa_manual': roa_m, 'roic_manual': roic_m, 'fcfroe': fcfroe,
            'roe_direct': row.get('return_on_equity'), 'roa_direct': row.get('return_on_assets'),
            'roic_direct': row.get('return_on_invested_capital'),
            'roce_fq': row.get('return_on_capital_employed_fq'), 'rotc_fq': row.get('return_on_total_capital_fq'),
            'pe': row.get('price_earnings_ttm'), 'ps': row.get('price_sales_ratio'),
            'pb': row.get('price_book_ratio'), 'pb_fq': row.get('price_book_fq'),
            'p_fcf': row.get('price_free_cash_flow_ttm'), 'ev_ebitda': row.get('enterprise_value_ebitda_ttm'),
            'div_yield': row.get('dividend_yield_recent'), 'div_yield_current': row.get('dividends_yield_current'),
            'div_yield_alt': row.get('dividends_yield'),
            'perf_3m': row.get('Perf.3M'), 'perf_6m': row.get('Perf.6M'), 'perf_12m': row.get('Perf.Y'),
            'f_score': row.get('piotroski_f_score_ttm'),
        }
    return results

def compare_metrics(borslabbet, tradingview):
    """Compare metrics and calculate accuracy."""
    matched = [(t, bl, tradingview.get(t) or tradingview.get(t.replace(' ', '_'))) 
               for t, bl in borslabbet.items() if tradingview.get(t) or tradingview.get(t.replace(' ', '_'))]
    
    print(f"\nMatched {len(matched)} stocks")
    
    metrics = [
        ('ROE (manual)', 'roe', 'roe_manual'), ('ROE (direct)', 'roe', 'roe_direct'),
        ('ROA (manual)', 'roa', 'roa_manual'), ('ROA (direct)', 'roa', 'roa_direct'),
        ('ROIC (manual)', 'roic', 'roic_manual'), ('ROIC (direct)', 'roic', 'roic_direct'),
        ('ROCE (fq)', 'roic', 'roce_fq'), ('ROTC (fq)', 'roic', 'rotc_fq'),
        ('FCFROE', 'fcfroe', 'fcfroe'),
        ('P/E', 'pe', 'pe'), ('P/S', 'ps', 'ps'),
        ('P/B (FY)', 'pb', 'pb'), ('P/B (MRQ)', 'pb', 'pb_fq'),
        ('P/FCF', 'p_fcf', 'p_fcf'), ('EV/EBITDA', 'ev_ebitda', 'ev_ebitda'),
        ('Div Yield (recent)', 'div_yield', 'div_yield'),
        ('Div Yield (current)', 'div_yield', 'div_yield_current'),
        ('Div Yield (alt)', 'div_yield', 'div_yield_alt'),
        ('Perf 3M', 'perf_3m', 'perf_3m'), ('Perf 6M', 'perf_6m', 'perf_6m'),
        ('Perf 12M', 'perf_12m', 'perf_12m'), ('F-Score', 'f_score', 'f_score'),
    ]
    
    print("\n" + "="*70)
    print(f"{'Metric':<22} {'N':>4} {'MAE':>8} {'<1pp':>6} {'<2pp':>6} {'<5pp':>6}")
    print("="*70)
    
    for name, bl_f, tv_f in metrics:
        errors = [abs(bl[bl_f] - tv[tv_f]) for _, bl, tv in matched if bl.get(bl_f) is not None and tv.get(tv_f) is not None]
        if errors:
            mae = sum(errors) / len(errors)
            w1 = sum(1 for e in errors if e <= 1) / len(errors) * 100
            w2 = sum(1 for e in errors if e <= 2) / len(errors) * 100
            w5 = sum(1 for e in errors if e <= 5) / len(errors) * 100
            print(f"{name:<22} {len(errors):>4} {mae:>8.2f} {w1:>5.0f}% {w2:>5.0f}% {w5:>5.0f}%")

if __name__ == "__main__":
    print("Loading Börslabbet data...")
    borslabbet = load_borslabbet_data()
    print(f"Loaded {len(borslabbet)} stocks")
    
    print("Fetching TradingView data...")
    tradingview = fetch_tradingview_data()
    print(f"Fetched {len(tradingview)} stocks")
    
    compare_metrics(borslabbet, tradingview)
