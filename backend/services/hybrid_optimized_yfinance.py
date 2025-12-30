"""
Hybrid ultra-optimized Yahoo Finance fetcher.
Combines yf.download() for prices + optimized individual calls for fundamentals.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class HybridYFinanceFetcher:
    """Hybrid fetcher: bulk prices + optimized fundamentals."""
    
    def __init__(self):
        self.ua = UserAgent()
        self.session_pool = []
        self._create_session_pool()
    
    def _create_session_pool(self, pool_size: int = 4):
        """Create pool of yfinance sessions with different user agents."""
        for i in range(pool_size):
            session = yf.Session()
            session.headers.update({
                'User-Agent': self.ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            self.session_pool.append(session)
    
    def get_session(self):
        """Get random session from pool."""
        return random.choice(self.session_pool)
    
    async def hybrid_bulk_fetch(self, tickers: List[str]) -> Dict[str, Dict]:
        """Hybrid approach: bulk prices + parallel fundamentals."""
        
        start_time = time.time()
        results = {}
        
        # Step 1: Try bulk price fetch (fast when it works)
        logger.info(f"Attempting bulk price fetch for {len(tickers)} stocks...")
        
        price_data = {}
        try:
            # Clean tickers for bulk download
            yahoo_tickers = [t if '.ST' in t else f"{t}.ST" for t in tickers]
            
            bulk_prices = yf.download(
                yahoo_tickers,
                period="1y",
                interval="1d",
                group_by='ticker',
                auto_adjust=True,
                prepost=False,
                threads=True,
                progress=False,
                timeout=30
            )
            
            if not bulk_prices.empty:
                for ticker in yahoo_tickers:
                    clean_ticker = ticker.replace('.ST', '')
                    try:
                        if len(yahoo_tickers) == 1:
                            # Single ticker case
                            price_series = bulk_prices['Close'].dropna()
                        else:
                            # Multiple tickers case
                            price_series = bulk_prices[ticker]['Close'].dropna()
                        
                        if not price_series.empty:
                            latest_price = float(price_series.iloc[-1])
                            price_data[clean_ticker] = {
                                'current_price': latest_price,
                                'price_history': price_series.tail(252).tolist()
                            }
                            logger.debug(f"✅ Bulk price for {clean_ticker}: {latest_price}")
                    except Exception as e:
                        logger.debug(f"Price extraction failed for {ticker}: {e}")
                
                logger.info(f"✅ Bulk prices: {len(price_data)}/{len(tickers)} successful")
            
        except Exception as e:
            logger.warning(f"Bulk price fetch failed: {e}")
        
        # Step 2: Parallel fundamental data fetch
        logger.info("Fetching fundamentals in parallel...")
        
        def fetch_stock_data(ticker: str) -> tuple[str, Dict]:
            """Fetch individual stock data with optimized session."""
            clean_ticker = ticker.replace('.ST', '')
            yahoo_ticker = ticker if '.ST' in ticker else f"{ticker}.ST"
            
            try:
                session = self.get_session()
                stock = yf.Ticker(yahoo_ticker, session=session)
                
                # Get info with timeout
                info = stock.info
                
                if not info or 'symbol' not in info:
                    return clean_ticker, {}
                
                # Extract key metrics
                result = {
                    'ticker': clean_ticker,
                    'name': info.get('longName', info.get('shortName', '')),
                    'sector': info.get('sector', ''),
                    'market_cap': info.get('marketCap', 0) / 1e6 if info.get('marketCap') else 0,
                    'pe': info.get('trailingPE'),
                    'pb': info.get('priceToBook'),
                    'ps': info.get('priceToSalesTrailing12Months'),
                    'ev_ebitda': info.get('enterpriseToEbitda'),
                    'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
                    'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None,
                    'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else None,
                    'current_ratio': info.get('currentRatio'),
                    'fetched_at': datetime.now()
                }
                
                # Add price data if we got it from bulk fetch
                if clean_ticker in price_data:
                    result.update(price_data[clean_ticker])
                else:
                    # Fallback: get current price from info
                    current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if current_price:
                        result['current_price'] = float(current_price)
                
                logger.debug(f"✅ Fetched {clean_ticker}: price={result.get('current_price')}, pe={result.get('pe')}")
                return clean_ticker, result
                
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                return clean_ticker, {}
        
        # Execute parallel fetching with controlled concurrency
        max_workers = 4
        successful = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(fetch_stock_data, ticker): ticker 
                for ticker in tickers
            }
            
            # Process completed tasks with small delays
            for i, future in enumerate(as_completed(future_to_ticker)):
                ticker, data = future.result()
                
                if data:
                    results[ticker] = data
                    successful += 1
                
                # Small delay between processing results
                if i < len(tickers) - 1:
                    await asyncio.sleep(0.5)
        
        duration = time.time() - start_time
        
        logger.info(f"✅ Hybrid fetch completed: {successful}/{len(tickers)} successful in {duration:.1f}s")
        logger.info(f"Speed: {len(tickers)/duration:.1f} stocks/second")
        
        return results

async def hybrid_optimized_sync(db, region: str = 'sweden', market_cap: str = 'large') -> Dict:
    """Ultra-optimized sync using hybrid approach."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting hybrid optimized sync: {len(tickers)} stocks")
        
        # Use hybrid fetcher
        fetcher = HybridYFinanceFetcher()
        results = await fetcher.hybrid_bulk_fetch(tickers)
        
        # Update database
        successful = 0
        for ticker, data in results.items():
            try:
                # Update Stock
                db.merge(Stock(
                    ticker=ticker,
                    name=data.get('name', ''),
                    market_cap_msek=data.get('market_cap', 0),
                    sector=data.get('sector', '')
                ))
                
                # Update Fundamentals
                db.merge(Fundamentals(
                    ticker=ticker,
                    fiscal_date=date.today(),
                    pe=data.get('pe'),
                    pb=data.get('pb'),
                    ps=data.get('ps'),
                    ev_ebitda=data.get('ev_ebitda'),
                    dividend_yield=data.get('dividend_yield'),
                    roe=data.get('roe'),
                    roa=data.get('roa'),
                    current_ratio=data.get('current_ratio'),
                    fetched_date=date.today()
                ))
                
                successful += 1
                
            except Exception as e:
                logger.error(f"Database error for {ticker}: {e}")
        
        db.commit()
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'HYBRID_OPTIMIZED_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'speed': f"{len(results)/duration:.1f} stocks/second",
            'method': 'Hybrid: bulk prices + parallel fundamentals',
            'optimization_level': 'MAXIMUM',
            'success_rate': f"{successful/len(tickers)*100:.1f}%" if tickers else "0%"
        }
        
    except Exception as e:
        logger.error(f"Hybrid optimized sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
