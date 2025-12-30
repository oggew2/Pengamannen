"""
TwelveData API fetcher with advanced caching and historical tracking.
Optimized for minimal API usage while maintaining data freshness.
"""
import requests
import time
from datetime import datetime, date
from typing import Dict, List, Optional
import logging
import asyncio
from services.advanced_cache import AdvancedCache, HistoricalTracker

logger = logging.getLogger(__name__)

class TwelveDataFetcher:
    """TwelveData API fetcher with state-of-the-art caching."""
    
    def __init__(self, api_key: str = "1621cba3a66040e088f94cf73e11d574"):
        self.api_key = api_key
        self.base_url = "https://api.twelvedata.com"
        self.session = requests.Session()
        self.calls_made = 0
        self.max_calls_per_minute = 8
        self.max_calls_per_day = 800
        
        # Initialize caching and tracking
        self.cache = AdvancedCache()
        self.tracker = HistoricalTracker()
        
        # Clean up expired cache on startup
        self.cache.cleanup_expired()
    
    async def rate_limit(self):
        """Smart rate limiting with cache awareness."""
        if self.calls_made % self.max_calls_per_minute == 0 and self.calls_made > 0:
            logger.info(f"Rate limiting: waiting 60s... (API calls saved by cache: {self.cache.get_cache_stats()['total_hits']})")
            await asyncio.sleep(60)
    
    def get_stock_quote(self, ticker: str) -> Optional[Dict]:
        """Get real-time quote with caching (TTL: 5 minutes for prices)."""
        try:
            # Convert Swedish ticker format: VOLV-B -> VOLV.B for TwelveData
            symbol = ticker.replace('-', '.')
            endpoint = "quote"
            params = {'symbol': symbol, 'apikey': self.api_key}
            
            # Check cache first
            cached_data = self.cache.get(endpoint, params)
            if cached_data:
                return cached_data
            
            # Make API call
            url = f"{self.base_url}/{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if 'close' in data and 'status' not in data:  # Success response
                    result = {
                        'current_price': float(data['close']),
                        'open': float(data.get('open', 0)),
                        'high': float(data.get('high', 0)),
                        'low': float(data.get('low', 0)),
                        'volume': int(data.get('volume', 0)),
                        'change': float(data.get('change', 0)),
                        'percent_change': float(data.get('percent_change', 0))
                    }
                    
                    # Cache for 5 minutes (prices change frequently)
                    self.cache.set(endpoint, params, result, ttl_hours=0.083)  # 5 minutes
                    
                    # Record in history
                    self.tracker.record_price(
                        ticker, 
                        result['current_price'], 
                        result['volume'], 
                        result['percent_change']
                    )
                    
                    return result
                else:
                    logger.debug(f"TwelveData quote error for {ticker}: {data}")
            
            return None
            
        except Exception as e:
            logger.error(f"TwelveData quote error for {ticker}: {e}")
            return None
    
    def get_fundamentals(self, ticker: str) -> Optional[Dict]:
        """Get fundamental data with caching (TTL: 24 hours for fundamentals)."""
        try:
            # Convert Swedish ticker format: VOLV-B -> VOLV.B for TwelveData
            symbol = ticker.replace('-', '.')
            endpoint = "profile"
            params = {'symbol': symbol, 'apikey': self.api_key}
            
            # Check cache first
            cached_data = self.cache.get(endpoint, params)
            if cached_data:
                return cached_data
            
            # Make API call
            url = f"{self.base_url}/{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                
                if 'name' in data and 'status' not in data:  # Success response
                    result = {
                        'name': data.get('name', ''),
                        'sector': data.get('sector', ''),
                        'market_cap': data.get('market_capitalization', 0) / 1e6 if data.get('market_capitalization') else 0,
                        'pe': data.get('pe_ratio'),
                        'pb': data.get('pb_ratio'),
                        'dividend_yield': data.get('dividend_yield', 0) * 100 if data.get('dividend_yield') else 0,
                        'roe': data.get('return_on_equity', 0) * 100 if data.get('return_on_equity') else None,
                        'description': data.get('description', '')
                    }
                    
                    # Cache for 24 hours (fundamentals change slowly)
                    self.cache.set(endpoint, params, result, ttl_hours=24)
                    
                    # Record in history
                    self.tracker.record_fundamentals(
                        ticker,
                        result['pe'],
                        result['pb'],
                        result['dividend_yield'],
                        result['roe'],
                        result['market_cap']
                    )
                    
                    return result
                else:
                    logger.debug(f"TwelveData fundamentals error for {ticker}: {data}")
            
            return {}
            
        except Exception as e:
            logger.error(f"TwelveData fundamentals error for {ticker}: {e}")
            return {}
    
    async def get_complete_data(self, ticker: str) -> Optional[Dict]:
        """Get complete stock data with intelligent caching."""
        try:
            # Rate limiting
            await self.rate_limit()
            
            # Get quote data (may be cached)
            quote_data = self.get_stock_quote(ticker)
            
            # Small delay between calls if both are API calls
            if quote_data and not self.cache.get("profile", {'symbol': f"{ticker}.STO", 'apikey': self.api_key}):
                await asyncio.sleep(8)  # Only delay if fundamentals not cached
            
            # Get fundamentals (may be cached)
            fundamental_data = self.get_fundamentals(ticker)
            
            if quote_data or fundamental_data:
                result = {
                    'ticker': ticker,
                    'fetched_at': datetime.now(),
                    'source': 'TwelveData',
                    'data_quality': 'CACHED' if (quote_data and fundamental_data) else 'LIVE'
                }
                
                # Merge data
                if quote_data:
                    result.update(quote_data)
                
                if fundamental_data:
                    result.update(fundamental_data)
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"TwelveData complete data error for {ticker}: {e}")
            return None
    
    async def fetch_multiple(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch multiple stocks with advanced caching."""
        results = {}
        successful = 0
        api_calls_made = 0
        cache_hits = 0
        
        # Get initial cache stats
        initial_stats = self.cache.get_cache_stats()
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"TwelveData: Starting fetch with advanced caching")
            await websocket_manager.send_log("info", f"Cache stats: {initial_stats['valid_entries']} valid entries, {initial_stats['total_hits']} total hits")
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Fetching {ticker} ({i+1}/{len(tickers)})")
            
            initial_calls = self.calls_made
            data = await self.get_complete_data(ticker)
            calls_for_this_stock = self.calls_made - initial_calls
            
            if data and (data.get('current_price') or data.get('name')):
                results[ticker] = data
                successful += 1
                api_calls_made += calls_for_this_stock
                
                if calls_for_this_stock == 0:
                    cache_hits += 1
                
                if websocket_manager:
                    price = data.get('current_price', 'N/A')
                    pe = data.get('pe', 'N/A')
                    cache_status = "CACHED" if calls_for_this_stock == 0 else f"{calls_for_this_stock} API calls"
                    await websocket_manager.send_log("success", f"✅ {ticker}: {price} SEK, P/E: {pe} ({cache_status})")
            else:
                if websocket_manager:
                    await websocket_manager.send_log("warning", f"❌ {ticker}: No data from TwelveData")
        
        # Final cache stats
        final_stats = self.cache.get_cache_stats()
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Fetch complete: {api_calls_made} API calls, {cache_hits} cache hits")
            await websocket_manager.send_log("info", f"Cache efficiency: {final_stats['cache_efficiency']}")
        
        logger.info(f"TwelveData fetch: {successful}/{len(tickers)} successful, {api_calls_made} API calls, {cache_hits} cache hits")
        return results

async def twelvedata_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Sync using TwelveData free API."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting TwelveData sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using TwelveData API - 800 calls/day FREE tier")
        
        # Use TwelveData fetcher with caching
        fetcher = TwelveDataFetcher()  # Uses your API key
        results = await fetcher.fetch_multiple(tickers, websocket_manager)
        
        # Update database
        successful = 0
        for ticker, data in results.items():
            try:
                db.merge(Stock(
                    ticker=ticker,
                    name=data.get('name', ''),
                    market_cap_msek=data.get('market_cap', 0),
                    sector=data.get('sector', '')
                ))
                
                # Add fundamentals if available
                if data.get('pe') or data.get('pb') or data.get('roe'):
                    db.merge(Fundamentals(
                        ticker=ticker,
                        fiscal_date=date.today(),
                        pe=data.get('pe'),
                        pb=data.get('pb'),
                        dividend_yield=data.get('dividend_yield'),
                        roe=data.get('roe'),
                        fetched_date=date.today()
                    ))
                
                successful += 1
                
            except Exception as e:
                logger.error(f"Database error for {ticker}: {e}")
        
        db.commit()
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'TWELVEDATA_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'TwelveData API - Free tier (800 calls/day)',
            'success_rate': f"{successful/len(results)*100:.1f}%" if results else "0%",
            'source': 'TwelveData',
            'cost': 'COMPLETELY FREE',
            'daily_limit': '800 API calls (400 stocks max)',
            'rate_limit': '8 calls/minute'
        }
        
    except Exception as e:
        logger.error(f"TwelveData sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
