"""
Alpha Vantage API fetcher - reliable backup for Swedish stocks.
Free tier: 25 calls/day, good for small portfolios.
"""
import requests
import time
from datetime import datetime, date
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class AlphaVantageFetcher:
    """Alpha Vantage API fetcher for Swedish stocks."""
    
    def __init__(self, api_key: str = "demo"):
        self.api_key = api_key  # Get free key from alphavantage.co
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()
    
    def get_stock_data(self, ticker: str) -> Optional[Dict]:
        """Get stock data from Alpha Vantage."""
        # Alpha Vantage format for Swedish stocks: VOLV-B.STO or STO:VOLV-B
        av_ticker = f"{ticker}.STO" if not ticker.endswith('.STO') else ticker
        
        try:
            # Get quote data
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': av_ticker,
                'apikey': self.api_key
            }
            
            response = self.session.get(self.base_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'Global Quote' in data:
                    quote = data['Global Quote']
                    return self._extract_quote_data(ticker.replace('.STO', ''), quote)
                elif 'Error Message' in data:
                    logger.warning(f"Alpha Vantage error for {ticker}: {data['Error Message']}")
                elif 'Note' in data:
                    logger.warning(f"Alpha Vantage rate limited: {data['Note']}")
            
            return None
            
        except Exception as e:
            logger.error(f"Alpha Vantage API error for {ticker}: {e}")
            return None
    
    def _extract_quote_data(self, ticker: str, quote: Dict) -> Dict:
        """Extract data from Alpha Vantage quote response."""
        try:
            return {
                'ticker': ticker,
                'name': ticker,  # Alpha Vantage doesn't provide company names in quotes
                'current_price': float(quote.get('05. price', 0)),
                'change_percent': float(quote.get('10. change percent', '0%').replace('%', '')),
                'volume': int(quote.get('06. volume', 0)),
                'fetched_at': datetime.now(),
                'source': 'AlphaVantage'
            }
        except Exception as e:
            logger.error(f"Data extraction error for {ticker}: {e}")
            return {
                'ticker': ticker,
                'current_price': None,
                'fetched_at': datetime.now(),
                'source': 'AlphaVantage_ERROR'
            }
    
    async def fetch_multiple(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch multiple stocks with Alpha Vantage rate limiting."""
        results = {}
        successful = 0
        
        # Alpha Vantage free tier: 25 calls/day, 5 calls/minute
        max_calls = min(len(tickers), 25)  # Respect daily limit
        
        for i, ticker in enumerate(tickers[:max_calls]):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Fetching {ticker} from Alpha Vantage ({i+1}/{max_calls})")
            
            data = self.get_stock_data(ticker)
            
            if data and data.get('current_price'):
                results[ticker] = data
                successful += 1
                
                if websocket_manager:
                    await websocket_manager.send_log("success", f"✅ {ticker}: Price {data.get('current_price')}")
            else:
                if websocket_manager:
                    await websocket_manager.send_log("warning", f"❌ {ticker}: No data from Alpha Vantage")
            
            # Rate limiting: 5 calls/minute
            if i < max_calls - 1:
                delay = 12  # 12 seconds between calls (5 calls/minute)
                if websocket_manager:
                    await websocket_manager.send_log("info", f"Rate limiting: waiting {delay}s...")
                time.sleep(delay)
        
        if len(tickers) > max_calls and websocket_manager:
            await websocket_manager.send_log("warning", f"Alpha Vantage free tier limited to {max_calls} stocks/day")
        
        logger.info(f"Alpha Vantage fetch completed: {successful}/{max_calls} successful")
        return results

async def alphavantage_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Sync using Alpha Vantage API."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting Alpha Vantage sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using Alpha Vantage API - 25 stocks/day limit")
        
        # Use Alpha Vantage fetcher
        fetcher = AlphaVantageFetcher()  # Uses demo key
        results = await fetcher.fetch_multiple(tickers, websocket_manager)
        
        # Update database
        successful = 0
        for ticker, data in results.items():
            try:
                db.merge(Stock(
                    ticker=ticker,
                    name=data.get('name', ticker),
                    market_cap_msek=0,  # Alpha Vantage quote doesn't include market cap
                    sector=''
                ))
                
                # Only basic price data available from quotes
                successful += 1
                
            except Exception as e:
                logger.error(f"Database error for {ticker}: {e}")
        
        db.commit()
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'ALPHAVANTAGE_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'Alpha Vantage API - reliable backup',
            'success_rate': f"{successful/len(results)*100:.1f}%" if results else "0%",
            'source': 'AlphaVantage',
            'limitation': '25 stocks/day on free tier'
        }
        
    except Exception as e:
        logger.error(f"Alpha Vantage sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
