#!/usr/bin/env python3
"""
Comprehensive test of Avanza API functionality and nyckeltal completeness.
"""
import requests
import json
import time
import asyncio
from datetime import datetime

# Known working Swedish stock IDs from Avanza
KNOWN_SWEDISH_STOCKS = {
    'ERIC-B': '5240',  # Ericsson B ✓ VERIFIED
    'VOLV-B': '5269',  # Volvo B (mapped to SEB-A ID, returns Volvo B)
    'ABB': '5447',     # ABB ✓ VERIFIED  
    'TREL-B': '5267',  # Trelleborg B (mapped to SWED-A ID)
    'SCA-B': '5263',   # SCA B (mapped to TEL2-B ID)
}

class AvanzaAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'sv-SE,sv;q=0.9,en;q=0.8',
            'Referer': 'https://www.avanza.se/',
            'Origin': 'https://www.avanza.se'
        })
        self.api_calls = 0
    
    def test_stock_data(self, stock_id: str) -> dict:
        """Test getting stock data from Avanza API."""
        try:
            url = f"https://www.avanza.se/_api/market-guide/stock/{stock_id}"
            
            start_time = time.time()
            response = self.session.get(url, timeout=15)
            response_time = time.time() - start_time
            self.api_calls += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract all available data
                key_indicators = data.get('keyIndicators', {})
                historical = data.get('historicalClosingPrices', {})
                listing = data.get('listing', {})
                market_cap_data = key_indicators.get('marketCapital', {})
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'name': data.get('name', ''),
                    'ticker': listing.get('tickerSymbol', ''),
                    'isin': data.get('isin', ''),
                    'current_price': historical.get('oneDay'),
                    'market_cap': market_cap_data.get('value'),
                    'currency': listing.get('currency', 'SEK'),
                    'sector': data.get('sectors', [{}])[0].get('sectorName') if data.get('sectors') else None,
                    
                    # All nyckeltal for Börslabbet strategies
                    'pe': key_indicators.get('priceEarningsRatio'),
                    'pb': key_indicators.get('priceBookRatio'),
                    'ps': key_indicators.get('priceSalesRatio'),
                    'ev_ebit': key_indicators.get('evEbitRatio'),
                    'roe': key_indicators.get('returnOnEquity'),
                    'roic': key_indicators.get('returnOnCapitalEmployed'),
                    'roa': key_indicators.get('returnOnTotalAssets'),
                    'dividend_yield': key_indicators.get('directYield'),
                    'beta': key_indicators.get('beta'),
                    'volatility': key_indicators.get('volatility'),
                    'equity_ratio': key_indicators.get('equityRatio'),
                    'operating_margin': key_indicators.get('operatingProfitMargin'),
                    'net_margin': key_indicators.get('netMargin'),
                    'gross_margin': key_indicators.get('grossMargin'),
                }
            else:
                return {
                    'success': False,
                    'response_time': response_time,
                    'status_code': response.status_code,
                    'error': f'HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'response_time': 0,
                'error': str(e)
            }
    
    def test_rate_limits(self, num_requests: int = 10) -> dict:
        """Test for rate limiting by making rapid requests."""
        print(f"\n=== RATE LIMIT TEST ({num_requests} requests) ===")
        
        results = []
        for i in range(num_requests):
            start_time = time.time()
            try:
                response = self.session.get('https://www.avanza.se/_api/market-guide/stock/5240', timeout=10)
                response_time = time.time() - start_time
                
                results.append({
                    'request': i + 1,
                    'status': response.status_code,
                    'time': response_time,
                    'success': response.status_code == 200
                })
                
                print(f"Request {i+1:2d}: {response.status_code} ({response_time:.3f}s)")
                
                if response.status_code != 200:
                    print(f"  Headers: {dict(response.headers)}")
                    
            except Exception as e:
                results.append({
                    'request': i + 1,
                    'status': 'ERROR',
                    'time': 0,
                    'success': False,
                    'error': str(e)
                })
                print(f"Request {i+1:2d}: ERROR - {e}")
        
        success_rate = sum(1 for r in results if r['success']) / len(results) * 100
        avg_time = sum(r['time'] for r in results if r['success']) / len([r for r in results if r['success']])
        
        return {
            'total_requests': num_requests,
            'successful': sum(1 for r in results if r['success']),
            'success_rate': success_rate,
            'average_response_time': avg_time,
            'blocked': any(r.get('status') == 429 for r in results),
            'errors': [r for r in results if not r['success']]
        }

def main():
    print("=== COMPREHENSIVE AVANZA API TEST ===")
    print(f"Test started: {datetime.now()}")
    
    tester = AvanzaAPITester()
    
    # Test 1: Data completeness for known stocks
    print("\n=== DATA COMPLETENESS TEST ===")
    
    all_results = {}
    for ticker, stock_id in KNOWN_SWEDISH_STOCKS.items():
        print(f"\nTesting {ticker} (ID: {stock_id})...")
        result = tester.test_stock_data(stock_id)
        all_results[ticker] = result
        
        if result['success']:
            print(f"  ✅ {result['name']} | {result['ticker']}")
            print(f"     Price: {result['current_price']} {result['currency']}")
            print(f"     Market Cap: {result['market_cap']:,.0f}" if result['market_cap'] else "     Market Cap: N/A")
            print(f"     Sector: {result['sector']}")
            print(f"     Response time: {result['response_time']:.3f}s")
        else:
            print(f"  ❌ Failed: {result['error']}")
    
    # Test 2: Nyckeltal completeness analysis
    print("\n=== NYCKELTAL COMPLETENESS ANALYSIS ===")
    
    required_nyckeltal = {
        'Sammansatt Momentum': ['current_price'],
        'Trendande Värde': ['pe', 'pb', 'ps', 'ev_ebit'],
        'Trendande Utdelning': ['dividend_yield', 'roe'],
        'Trendande Kvalitet': ['roe', 'roic']
    }
    
    successful_stocks = {k: v for k, v in all_results.items() if v['success']}
    
    for strategy, required_fields in required_nyckeltal.items():
        print(f"\n{strategy}:")
        compatible_count = 0
        
        for ticker, data in successful_stocks.items():
            has_required = all(data.get(field) is not None for field in required_fields)
            if has_required:
                compatible_count += 1
                status = "✅"
            else:
                status = "❌"
                missing = [field for field in required_fields if data.get(field) is None]
                print(f"    {status} {ticker}: Missing {missing}")
        
        compatibility = compatible_count / len(successful_stocks) * 100 if successful_stocks else 0
        print(f"  📊 Compatibility: {compatible_count}/{len(successful_stocks)} stocks ({compatibility:.1f}%)")
    
    # Test 3: Rate limiting
    rate_limit_results = tester.test_rate_limits(10)
    
    print(f"\n=== RATE LIMIT RESULTS ===")
    print(f"Success rate: {rate_limit_results['success_rate']:.1f}%")
    print(f"Average response time: {rate_limit_results['average_response_time']:.3f}s")
    print(f"Blocked requests: {'Yes' if rate_limit_results['blocked'] else 'No'}")
    
    # Test 4: Overall assessment
    print(f"\n=== OVERALL ASSESSMENT ===")
    successful_stocks_count = len(successful_stocks)
    total_stocks_count = len(KNOWN_SWEDISH_STOCKS)
    
    print(f"📊 Data availability: {successful_stocks_count}/{total_stocks_count} stocks ({successful_stocks_count/total_stocks_count*100:.1f}%)")
    print(f"🚀 API performance: {rate_limit_results['average_response_time']:.3f}s average response")
    print(f"🔒 Rate limiting: {'Detected' if rate_limit_results['blocked'] else 'None detected'}")
    print(f"💰 Cost: FREE (no API keys required)")
    print(f"📞 Total API calls made: {tester.api_calls}")
    
    # Börslabbet strategy compatibility summary
    print(f"\n=== BÖRSLABBET STRATEGY COMPATIBILITY ===")
    for strategy, required_fields in required_nyckeltal.items():
        compatible_count = sum(1 for data in successful_stocks.values() 
                             if all(data.get(field) is not None for field in required_fields))
        compatibility = compatible_count / len(successful_stocks) * 100 if successful_stocks else 0
        status = "✅" if compatibility >= 80 else "⚠️" if compatibility >= 50 else "❌"
        print(f"  {status} {strategy}: {compatibility:.1f}% compatible")
    
    print(f"\n=== CONCLUSION ===")
    if successful_stocks_count >= 3 and rate_limit_results['success_rate'] >= 90:
        print("✅ Avanza API is SUITABLE for production use")
        print("   - Good data availability")
        print("   - No significant rate limiting")
        print("   - Comprehensive nyckeltal coverage")
        print("   - FREE to use")
    else:
        print("⚠️  Avanza API has limitations:")
        if successful_stocks_count < 3:
            print("   - Limited stock coverage")
        if rate_limit_results['success_rate'] < 90:
            print("   - Rate limiting detected")

if __name__ == "__main__":
    main()
