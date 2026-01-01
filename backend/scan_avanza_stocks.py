#!/usr/bin/env python3
"""
Avanza Stock Scanner - Scans for Stockholmsbörsen and First North stocks.

Usage:
    cd /Users/ewreosk/Kiro/borslabbet-app/backend
    source ../venv/bin/activate
    python scan_avanza_stocks.py

This will scan Avanza IDs and output stocks grouped by market.
Takes about 30-60 minutes to complete full scan.
"""

import requests
import time
import json
from datetime import datetime

def scan_range(session, start, end, delay=0.02):
    """Scan a range of Avanza stock IDs."""
    stockholmsborsen = []
    first_north = []
    other = []
    
    for stock_id in range(start, end):
        try:
            r = session.get(f'https://www.avanza.se/_api/market-guide/stock/{stock_id}', timeout=3)
            if r.status_code == 200:
                data = r.json()
                ticker = data.get('listing', {}).get('tickerSymbol', '')
                market = data.get('listing', {}).get('marketPlaceName', '')
                name = data.get('name', '')
                
                if ticker:
                    entry = {"id": str(stock_id), "ticker": ticker, "name": name, "market": market}
                    
                    if 'Stockholmsbörsen' in market:
                        stockholmsborsen.append(entry)
                        print(f"    ✅ STHLM: {ticker} - {name[:40]}")
                    elif 'First North' in market:
                        first_north.append(entry)
                        print(f"    🔵 FN: {ticker} - {name[:40]}")
        except Exception as e:
            pass
        
        time.sleep(delay)
        
        # Progress update every 500 IDs
        if stock_id % 500 == 0 and stock_id > start:
            pct = (stock_id - start) / (end - start) * 100
            print(f"  [{pct:.0f}%] ID {stock_id} | Found: {len(stockholmsborsen)} STHLM, {len(first_north)} FN")
    
    return stockholmsborsen, first_north, other


def main():
    print("=" * 60)
    print("AVANZA STOCK SCANNER")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.avanza.se/'
    })
    
    all_stockholmsborsen = []
    all_first_north = []
    
    # Scan ranges where stocks are likely to be found
    ranges = [
        (0, 10000),      # Main range - most stocks here
        (10000, 50000),  # Extended range
        (50000, 100000), # Higher IDs
        (100000, 200000), # Even higher
        (200000, 400000), # Newer stocks
        (400000, 600000), # Recent additions
    ]
    
    for start, end in ranges:
        print(f"\n--- Scanning range {start}-{end} ---")
        sthlm, fn, _ = scan_range(session, start, end)
        all_stockholmsborsen.extend(sthlm)
        all_first_north.extend(fn)
        print(f"Range complete. Running totals: Stockholmsbörsen={len(all_stockholmsborsen)}, First North={len(all_first_north)}")
    
    # Output results
    print("\n" + "=" * 60)
    print("SCAN COMPLETE")
    print("=" * 60)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTotal Stockholmsbörsen: {len(all_stockholmsborsen)}")
    print(f"Total First North: {len(all_first_north)}")
    
    # Save to JSON file
    output = {
        "scan_date": datetime.now().isoformat(),
        "stockholmsborsen": all_stockholmsborsen,
        "first_north": all_first_north
    }
    
    with open("avanza_stocks_scan.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: avanza_stocks_scan.json")
    
    # Also print in format ready for code
    print("\n" + "=" * 60)
    print("STOCKHOLMSBÖRSEN STOCKS (copy this):")
    print("=" * 60)
    for s in sorted(all_stockholmsborsen, key=lambda x: x['ticker']):
        ticker_clean = s['ticker'].replace(' ', '-')
        print(f'            "{ticker_clean}": "{s["id"]}",  # {s["name"][:30]}')
    
    print("\n" + "=" * 60)
    print("FIRST NORTH STOCKS (copy this):")
    print("=" * 60)
    for s in sorted(all_first_north, key=lambda x: x['ticker']):
        ticker_clean = s['ticker'].replace(' ', '-')
        print(f'            "{ticker_clean}": "{s["id"]}",  # {s["name"][:30]}')


if __name__ == "__main__":
    main()
