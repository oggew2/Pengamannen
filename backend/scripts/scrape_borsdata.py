#!/usr/bin/env python3
"""
Scrape historical fundamentals from Börsdata.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/scrape_borsdata.py

Output saved to:
    data/borsdata_fundamentals.json (working file)
    data/backups/borsdata_YYYYMMDD_HHMMSS.json (permanent backup)
"""

import json
import random
import time
import shutil
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
BACKUP_DIR = DATA_DIR / "backups"
OUTPUT_FILE = DATA_DIR / "borsdata_fundamentals.json"
STOCKS_FILE = DATA_DIR / "borsdata_stocks.json"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def setup_browser(playwright):
    browser = playwright.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled'],
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    )
    page = context.new_page()
    page.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined});')
    return browser, page


def fetch_stocks(page):
    """Fetch all Swedish stocks."""
    seen_ids = set()
    stocks = []
    skip = 0
    
    log("  Fetching stocks (filtering Swedish only)...")
    
    while True:
        resp = page.evaluate(f'''async () => {{
            const r = await fetch('/api/terminal/screener/kpis/data', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    filter: {{instrumentTypes: [0]}},
                    kpis: [],
                    skip: {skip},
                    take: 100
                }})
            }});
            return r.ok ? await r.json() : null;
        }}''')
        
        if not resp or 'data' not in resp:
            break
        
        batch = resp['data']
        if not batch:
            break
        
        # Filter Swedish only (countryId=1 or countryShortName=SWE)
        for s in batch:
            cid = s.get('companyId')
            if cid and cid not in seen_ids and s.get('countryId') == 1:
                seen_ids.add(cid)
                stocks.append(s)
        
        log(f"  Swedish: {len(stocks)} (scanned {skip + len(batch)})")
        
        skip += 100
        
        # Stop after scanning enough (Swedish stocks are ~700-800)
        if skip > 2000 and len(stocks) > 600:
            break
        if skip > 5000:
            break
            
        time.sleep(0.1)
    
    log(f"  TOTAL: {len(stocks)} Swedish stocks")
    return stocks


def fetch_stock_info(page, company_id):
    """Fetch stock metadata."""
    try:
        resp = page.evaluate(f'''async () => {{
            const r = await fetch('/api/terminal/instruments/{company_id}/latestGeneralInfo');
            return r.ok ? await r.json() : null;
        }}''')
        if resp:
            return {
                'sector': resp.get('sector'),
                'industry': resp.get('industry'),
                'market': resp.get('market'),
                'isin': resp.get('isin'),
            }
    except:
        pass
    return {}


def fetch_report_dates(page, ticker):
    """Fetch report publication dates."""
    try:
        resp = page.evaluate(f'''async () => {{
            const r = await fetch('/api/terminal/ta/reports?symbol={ticker}');
            return r.ok ? await r.json() : null;
        }}''')
        return resp or []
    except:
        return []


def fetch_price_history(page, ticker):
    """Fetch full price history (up to 28 years)."""
    try:
        resp = page.evaluate(f'''async () => {{
            const r = await fetch('/api/terminal/ta/history?symbol={ticker}&resolution=1D&from=0&to=2000000000&countback=10000');
            return r.ok ? await r.json() : null;
        }}''')
        if resp and resp.get('s') == 'ok':
            return {
                't': resp.get('t', []),
                'o': resp.get('o', []),
                'h': resp.get('h', []),
                'l': resp.get('l', []),
                'c': resp.get('c', []),
                'v': resp.get('v', []),
            }
    except:
        pass
    return None


def fetch_fundamentals(page, company_id):
    """Fetch quarterly + annual fundamentals."""
    data = {'quarterly': {}, 'annual': {}}
    
    field_map = {
        2: 'pe', 3: 'ps', 10: 'ev_ebit', 19: 'peg',
        33: 'roe', 34: 'roa', 35: 'roa_tangible', 36: 'roc', 37: 'roic',
        28: 'gross_margin', 29: 'ebit_margin', 30: 'profit_margin', 31: 'fcf_margin', 32: 'ebitda_margin',
        1: 'dividend_yield', 7: 'dividend_per_share', 20: 'payout_ratio', 26: 'dividend_fcf_ratio',
        5: 'revenue_per_share', 6: 'eps', 8: 'book_value_per_share', 23: 'fcf_per_share',
        53: 'revenue', 54: 'ebitda', 55: 'ebit', 56: 'net_income',
        57: 'total_assets', 58: 'equity', 60: 'net_debt', 61: 'shares',
        62: 'operating_cf', 63: 'fcf', 64: 'capex', 130: 'cash',
        132: 'long_term_debt', 133: 'short_term_debt', 135: 'gross_profit',
        39: 'equity_ratio', 40: 'debt_equity', 44: 'current_ratio', 42: 'net_debt_ebitda',
        38: 'asset_turnover', 51: 'operating_cf_margin',
    }
    
    # Quarterly (all report types in parallel-ish)
    for rt in range(1, 6):
        try:
            resp = page.evaluate(f'''async () => {{
                const r = await fetch('/api/terminal/instruments/{company_id}/analysis/finances/report?reportType={rt}&periodType=1&years=15');
                return r.ok ? await r.json() : null;
            }}''')
            if resp:
                for kpi in resp.get('kpisHistories', []):
                    field = field_map.get(kpi.get('kpiId'))
                    if field:
                        for v in kpi.get('orderedHistoryValues', []):
                            date_key = v.get('period', {}).get('date', '')[:10]
                            val = v.get('value')
                            if date_key and val is not None:
                                data['quarterly'].setdefault(date_key, {})[field] = val
        except:
            pass
    
    # Annual (for dividend yield/payout)
    try:
        resp = page.evaluate(f'''async () => {{
            const r = await fetch('/api/terminal/instruments/{company_id}/analysis/finances/report?reportType=1&periodType=0&years=20');
            return r.ok ? await r.json() : null;
        }}''')
        if resp:
            for kpi in resp.get('kpisHistories', []):
                field = field_map.get(kpi.get('kpiId'))
                if field:
                    for v in kpi.get('orderedHistoryValues', []):
                        year = v.get('period', {}).get('year')
                        val = v.get('value')
                        if year and val is not None:
                            data['annual'].setdefault(year, {})[field] = val
    except:
        pass
    
    return data


def save_backup(data):
    """Save permanent backup copy."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f"borsdata_{timestamp}.json"
    with open(backup_file, 'w') as f:
        json.dump(data, f)
    log(f"Backup saved: {backup_file.name}")


def main():
    from playwright.sync_api import sync_playwright
    
    DATA_DIR.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("BÖRSDATA SCRAPER")
    print("=" * 60)
    print("Ctrl+C to stop - progress saved after each stock")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 60 + "\n")
    
    all_data = json.load(open(OUTPUT_FILE)) if OUTPUT_FILE.exists() else {}
    completed = set(all_data.keys())
    log(f"Resuming: {len(completed)} stocks already done")
    
    with sync_playwright() as p:
        browser, page = setup_browser(p)
        try:
            log("Connecting...")
            page.goto('https://borsdata.se/terminal/en/axfood/analysis', wait_until='networkidle')
            page.wait_for_timeout(3000)
            
            if 'Cloudflare' in page.title():
                log("ERROR: Cloudflare block. Wait and retry.")
                return
            
            log("Connected!\n")
            
            # Get stocks
            if STOCKS_FILE.exists():
                stocks = json.load(open(STOCKS_FILE))
                log(f"Loaded {len(stocks)} stocks from cache")
            else:
                log("Fetching stock list...")
                stocks = fetch_stocks(page)
                json.dump(stocks, open(STOCKS_FILE, 'w'))
            
            remaining = [s for s in stocks if str(s['companyId']) not in completed]
            log(f"Remaining: {len(remaining)}/{len(stocks)}\n")
            
            if not remaining:
                log("All done!")
                return
            
            start_time = time.time()
            
            for i, s in enumerate(remaining):
                cid = str(s['companyId'])
                ticker = s.get('shortName', '?')
                name = s.get('name', '?')
                url_name = s.get('countryUrlName', ticker.lower())
                
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - i - 1) / rate / 60 if rate > 0 else 0
                pct = (len(completed) + 1) / len(stocks) * 100
                
                print(f"[{len(completed)+1}/{len(stocks)}] ({pct:.0f}%) {ticker:8} ", end='', flush=True)
                
                try:
                    # Navigate to stock's page first (required for API access)
                    page.goto(f'https://borsdata.se/terminal/en/{url_name}/analysis', wait_until='networkidle')
                    page.wait_for_timeout(1500)
                    
                    info = fetch_stock_info(page, cid)
                    fund = fetch_fundamentals(page, cid)
                    reports = fetch_report_dates(page, ticker)
                    prices = fetch_price_history(page, ticker)
                    
                    all_data[cid] = {
                        'name': name, 'ticker': ticker,
                        'sector': info.get('sector'), 'industry': info.get('industry'),
                        'market': info.get('market'), 'isin': info.get('isin'),
                        'fundamentals': fund, 'report_dates': reports, 'prices': prices,
                    }
                    completed.add(cid)
                    json.dump(all_data, open(OUTPUT_FILE, 'w'))
                    
                    q = len(fund.get('quarterly', {}))
                    d = len(prices.get('t', [])) if prices else 0
                    print(f"✓ {q:2}q {d:5}d | ETA {eta:.0f}m")
                    
                    time.sleep(random.uniform(0.5, 1.0))
                    
                except KeyboardInterrupt:
                    print("\n")
                    log("Stopped. Saving backup...")
                    save_backup(all_data)
                    return
                except Exception as e:
                    print(f"ERR: {e}")
            
            print()
            log("Complete!")
            save_backup(all_data)
            log(f"Total: {len(all_data)} stocks")
            
        finally:
            browser.close()


if __name__ == '__main__':
    main()
