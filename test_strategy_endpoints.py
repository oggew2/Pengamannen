#!/usr/bin/env python3
"""
Test strategy endpoints return exactly 10 stocks with correct ranking order
"""
import requests
import json

def test_strategy_endpoints():
    """Test all 4 strategy endpoints return exactly 10 stocks with correct ranking."""
    base_url = "http://localhost:8000"
    
    strategies = [
        'sammansatt_momentum',
        'trendande_varde', 
        'trendande_utdelning',
        'trendande_kvalitet'
    ]
    
    print("🔍 TESTING STRATEGY ENDPOINTS...")
    
    for strategy in strategies:
        print(f"\n📊 Testing {strategy}...")
        
        try:
            response = requests.get(f"{base_url}/v1/strategies/{strategy}")
            
            if response.status_code != 200:
                print(f"❌ FAIL: {strategy} returned status {response.status_code}")
                continue
                
            data = response.json()
            
            # Check exactly 10 stocks
            if len(data) != 10:
                print(f"❌ FAIL: {strategy} returned {len(data)} stocks, expected 10")
                continue
                
            # Check ranking order (score should be descending)
            scores = [stock.get('score', 0) for stock in data]
            if scores != sorted(scores, reverse=True):
                print(f"❌ FAIL: {strategy} not properly ranked by score")
                print(f"   Scores: {scores}")
                continue
                
            print(f"✅ PASS: {strategy} - 10 stocks, properly ranked")
            print(f"   Top stock: {data[0]['ticker']} (score: {data[0].get('score', 'N/A')})")
            
        except Exception as e:
            print(f"❌ ERROR: {strategy} failed with {e}")
    
    print("\n🎯 Strategy endpoint testing complete!")

if __name__ == "__main__":
    test_strategy_endpoints()
