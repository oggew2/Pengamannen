"""
AvanzaPy fetcher - Free Swedish stock data from Avanza's unofficial API.
No login required, works with Swedish stocks directly.
"""
import requests
import time
from datetime import datetime, date
from typing import Dict, List, Optional
import logging
import asyncio
from services.advanced_cache import AdvancedCache, HistoricalTracker

logger = logging.getLogger(__name__)

class AvanzaFetcher:
    """Avanza unofficial API fetcher for Swedish stocks."""
    
    def __init__(self):
        self.base_url = "https://www.avanza.se/_api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'sv-SE,sv;q=0.9,en;q=0.8',
            'Referer': 'https://www.avanza.se/'
        })
        
        # Initialize caching and tracking
        self.cache = AdvancedCache()
        self.tracker = HistoricalTracker()
        self.calls_made = 0
    
    def search_stock(self, name: str) -> List[Dict]:
        """Search for Swedish stocks by name."""
        try:
            url = f"{self.base_url}/search/global-search/global-search-template"
            params = {
                'query': name,
                'limit': 10
            }
            
            response = self.session.get(url, params=params, timeout=10)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                
                stocks = []
                for hit in data.get('hits', []):
                    if hit.get('instrumentType') == 'STOCK' and hit.get('market', {}).get('country') == 'SE':
                        stocks.append({
                            'id': hit.get('id'),
                            'name': hit.get('name'),
                            'ticker': hit.get('ticker'),
                            'market': hit.get('market', {}).get('name'),
                            'currency': hit.get('currency')
                        })
                
                return stocks
            
            return []
            
        except Exception as e:
            logger.error(f"Avanza search error for {name}: {e}")
            return []
    
    def get_stock_data(self, stock_id: str) -> Optional[Dict]:
        """Get detailed stock data from Avanza."""
        try:
            endpoint = f"stock/{stock_id}"
            params = {'stock_id': stock_id}
            
            # Check cache first
            cached_data = self.cache.get(endpoint, params)
            if cached_data:
                return cached_data
            
            url = f"{self.base_url}/market-guide/stock/{stock_id}"
            
            response = self.session.get(url, timeout=10)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract key data
                result = {
                    'id': stock_id,
                    'name': data.get('name', ''),
                    'ticker': data.get('ticker', ''),
                    'current_price': data.get('quote', {}).get('last'),
                    'change_percent': data.get('quote', {}).get('changePercent'),
                    'volume': data.get('quote', {}).get('totalVolumeTraded'),
                    'market_cap': data.get('keyRatios', {}).get('marketCapital'),
                    'pe': data.get('keyRatios', {}).get('priceEarningsRatio'),
                    'pb': data.get('keyRatios', {}).get('priceToBookRatio'),
                    'ps': data.get('keyRatios', {}).get('priceSalesRatio'),
                    'dividend_yield': data.get('keyRatios', {}).get('dividendYield'),
                    'roe': data.get('keyRatios', {}).get('returnOnEquity'),
                    'sector': data.get('company', {}).get('sector'),
                    'description': data.get('company', {}).get('description'),
                    'fetched_at': datetime.now(),
                    'source': 'Avanza'
                }
                
                # Cache for 5 minutes
                self.cache.set(endpoint, params, result, ttl_hours=0.083)
                
                # Record in history
                if result['current_price']:
                    self.tracker.record_price(
                        result['ticker'],
                        result['current_price'],
                        result['volume'],
                        result['change_percent']
                    )
                
                if result['pe'] or result['roe']:
                    self.tracker.record_fundamentals(
                        result['ticker'],
                        result['pe'],
                        result['pb'],
                        result['dividend_yield'],
                        result['roe'],
                        result['market_cap']
                    )
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Avanza stock data error for {stock_id}: {e}")
            return None
    
    def find_and_get_stock(self, ticker: str) -> Optional[Dict]:
        """Find stock by ticker and get its data."""
        try:
            # First search for the stock
            search_results = self.search_stock(ticker)
            
            if not search_results:
                logger.debug(f"No search results for {ticker}")
                return None
            
            # Find exact ticker match
            for stock in search_results:
                if stock['ticker'] == ticker or stock['ticker'] == ticker.replace('-', ''):
                    stock_id = stock['id']
                    logger.debug(f"Found {ticker} with ID {stock_id}")
                    
                    # Get detailed data
                    return self.get_stock_data(stock_id)
            
            # If no exact match, try first result
            if search_results:
                stock_id = search_results[0]['id']
                logger.debug(f"Using first result for {ticker}: ID {stock_id}")
                return self.get_stock_data(stock_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Avanza find and get error for {ticker}: {e}")
            return None
    
    async def fetch_multiple(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch multiple Swedish stocks from Avanza."""
        results = {}
        successful = 0
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Avanza: Fetching {len(tickers)} Swedish stocks")
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Searching Avanza for {ticker} ({i+1}/{len(tickers)})")
            
            data = self.find_and_get_stock(ticker)
            
            if data and data.get('current_price'):
                results[ticker] = data
                successful += 1
                
                if websocket_manager:
                    price = data.get('current_price', 'N/A')
                    pe = data.get('pe', 'N/A')
                    name = data.get('name', 'N/A')[:30]
                    await websocket_manager.send_log("success", f"✅ {ticker}: {name} | {price} SEK | P/E: {pe}")
            else:
                if websocket_manager:
                    await websocket_manager.send_log("warning", f"❌ {ticker}: Not found on Avanza")
            
            # Small delay to be respectful
            if i < len(tickers) - 1:
                await asyncio.sleep(1)
        
        # Cache stats
        cache_stats = self.cache.get_cache_stats()
        if websocket_manager:
            await websocket_manager.send_log("info", f"Avanza fetch complete: {successful}/{len(tickers)} successful")
            await websocket_manager.send_log("info", f"API calls: {self.calls_made}, Cache hits: {cache_stats['total_hits']}")
        
        logger.info(f"Avanza fetch: {successful}/{len(tickers)} successful, {self.calls_made} API calls")
        return results

async def avanza_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Sync using Avanza unofficial API."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting Avanza sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using Avanza unofficial API - FREE Swedish stock data")
        
        # Use Avanza fetcher
        fetcher = AvanzaFetcher()
        results = await fetcher.fetch_multiple(tickers, websocket_manager)
        
        # Update database
        successful = 0
        for ticker, data in results.items():
            try:
                db.merge(Stock(
                    ticker=ticker,
                    name=data.get('name', ''),
                    market_cap_msek=data.get('market_cap', 0) / 1e6 if data.get('market_cap') else 0,
                    sector=data.get('sector', '')
                ))
                
                # Add fundamentals if available
                if data.get('pe') or data.get('pb') or data.get('roe'):
                    db.merge(Fundamentals(
                        ticker=ticker,
                        fiscal_date=date.today(),
                        pe=data.get('pe'),
                        pb=data.get('pb'),
                        ps=data.get('ps'),
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
            'status': 'AVANZA_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'Avanza unofficial API - FREE Swedish stocks',
            'success_rate': f"{successful/len(tickers)*100:.1f}%" if tickers else "0%",
            'source': 'Avanza',
            'cost': 'COMPLETELY FREE',
            'coverage': 'Swedish stocks with full fundamentals',
            'api_calls': fetcher.calls_made
        }
        
    except Exception as e:
        logger.error(f"Avanza sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
