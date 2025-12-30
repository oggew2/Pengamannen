"""
Hybrid data fetcher: Avanza fundamentals + Yahoo Finance historical prices.
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from services.avanza_fetcher_v2 import AvanzaDirectFetcher
import asyncio
from services.smart_cache import smart_cache

logger = logging.getLogger(__name__)

class HybridDataFetcher:
    """Combines Avanza fundamentals with Yahoo Finance historical prices."""
    
    def __init__(self):
        self.avanza_fetcher = AvanzaDirectFetcher()
        self.current_sync_generation = int(datetime.now().timestamp())
    
    def get_historical_prices(self, ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Get historical prices from Yahoo Finance with smart caching."""
        
        # Convert ticker format for Yahoo Finance (Swedish stocks)
        # ERIC-B -> ERIC-B.ST, but handle special cases
        if not ticker.endswith('.ST'):
            yf_ticker = f"{ticker}.ST"
        else:
            yf_ticker = ticker
        
        cache_key = f"historical_prices_{yf_ticker}_{period}"
        
        # Check cache first (cache for 24 hours)
        cached_data = smart_cache.get("historical_prices", {"ticker": yf_ticker, "period": period})
        
        if cached_data and not cached_data.get('_cache_metadata', {}).get('is_expired', False):
            logger.debug(f"Using cached historical prices for {ticker}")
            # Convert back to DataFrame
            df = pd.DataFrame(cached_data['prices'])
            df['date'] = pd.to_datetime(df['date'])
            return df
        
        try:
            # Fetch from Yahoo Finance
            stock = yf.Ticker(yf_ticker)
            hist = stock.history(period=period)
            
            if hist.empty:
                logger.warning(f"No historical data for {yf_ticker}")
                return None
            
            # Convert to our format
            df = pd.DataFrame({
                'ticker': ticker,  # Use original ticker format
                'date': hist.index,
                'close': hist['Close'].values,
                'volume': hist['Volume'].values
            })
            
            # Cache the data (24 hour TTL)
            cache_data = {
                'prices': df.to_dict('records'),
                'fetched_at': datetime.now().isoformat()
            }
            
            smart_cache.set(
                "historical_prices", 
                {"ticker": yf_ticker, "period": period}, 
                cache_data,
                ttl_hours=24,
                sync_generation=self.current_sync_generation
            )
            
            logger.debug(f"Fetched and cached historical prices for {ticker}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch historical prices for {ticker}: {e}")
            return None
    
    def get_complete_stock_data(self, ticker: str) -> Dict:
        """Get complete stock data: Avanza fundamentals + historical prices."""
        
        # Get Avanza stock ID
        stock_id = self.avanza_fetcher.known_stocks.get(ticker)
        if not stock_id:
            logger.warning(f"No Avanza mapping for {ticker}")
            return {}
        
        # Get fundamentals from Avanza (with smart caching)
        fundamentals = self.avanza_fetcher.get_stock_overview(stock_id)
        if not fundamentals:
            logger.warning(f"No fundamental data for {ticker}")
            return {}
        
        # Get historical prices
        historical_prices = self.get_historical_prices(ticker)
        
        # Combine data
        complete_data = {
            **fundamentals,
            'has_historical_prices': historical_prices is not None,
            'historical_data_points': len(historical_prices) if historical_prices is not None else 0
        }
        
        if historical_prices is not None:
            # Add momentum indicators
            complete_data['price_history_available'] = True
            complete_data['oldest_price_date'] = historical_prices['date'].min().isoformat()
            complete_data['latest_price_date'] = historical_prices['date'].max().isoformat()
        else:
            complete_data['price_history_available'] = False
        
        return complete_data
    
    async def fetch_multiple_complete(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch complete data for multiple stocks."""
        results = {}
        successful = 0
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Hybrid fetch: {len(tickers)} stocks (Avanza + Yahoo)")
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Fetching {ticker} ({i+1}/{len(tickers)})")
            
            try:
                data = self.get_complete_stock_data(ticker)
                
                if data and data.get('current_price'):
                    results[ticker] = data
                    successful += 1
                    
                    if websocket_manager:
                        price = data.get('current_price', 'N/A')
                        has_history = '📈' if data.get('price_history_available') else '📊'
                        nyckeltal_count = sum(1 for f in ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda', 'dividend_yield', 'roe', 'roa', 'roic', 'fcfroe'] if data.get(f) is not None)
                        await websocket_manager.send_log("success", f"✅ {ticker}: {data.get('name', 'N/A')[:20]} | {price} SEK | {nyckeltal_count}/10 nyckeltal {has_history}")
                else:
                    if websocket_manager:
                        await websocket_manager.send_log("warning", f"❌ {ticker}: No data available")
                
            except Exception as e:
                logger.error(f"Error fetching {ticker}: {e}")
                if websocket_manager:
                    await websocket_manager.send_log("error", f"❌ {ticker}: Error - {str(e)[:50]}")
            
            # Small delay to be respectful
            if i < len(tickers) - 1:
                await asyncio.sleep(1)
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Hybrid fetch complete: {successful}/{len(tickers)} successful")
        
        return results

# Global hybrid fetcher
hybrid_fetcher = HybridDataFetcher()
