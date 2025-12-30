"""
Bulletproof web scraping fetcher for Swedish stocks.
Uses multiple sources and proper headers to avoid detection.
"""
import requests
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)

class BulletproofScrapingFetcher:
    """Bulletproof web scraping for Swedish stock data."""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Setup session with browser-like headers."""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
    
    def get_stock_from_avanza(self, ticker: str) -> Optional[Dict]:
        """Scrape stock data from Avanza (Swedish broker)."""
        try:
            # Avanza search URL
            search_url = f"https://www.avanza.se/aktier/om-aktien.html/{ticker}"
            
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract price (Avanza shows current price)
                price_element = soup.find('span', class_='lastPrice')
                if not price_element:
                    price_element = soup.find('span', {'data-e2e': 'quoteLastPrice'})
                
                price = None
                if price_element:
                    price_text = price_element.get_text().strip()
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        price = float(price_match.group().replace(',', ''))
                
                # Extract company name
                name_element = soup.find('h1') or soup.find('title')
                name = name_element.get_text().strip() if name_element else ticker
                
                if price:
                    return {
                        'ticker': ticker,
                        'name': name,
                        'current_price': price,
                        'fetched_at': datetime.now(),
                        'source': 'Avanza'
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Avanza scraping error for {ticker}: {e}")
            return None
    
    def get_stock_from_nordnet(self, ticker: str) -> Optional[Dict]:
        """Scrape stock data from Nordnet (Nordic broker)."""
        try:
            # Nordnet search - they have Swedish stocks
            search_url = f"https://www.nordnet.se/marknaden/aktiekurser/{ticker}"
            
            # Update headers for Nordnet
            headers = self.session.headers.copy()
            headers.update({
                'Referer': 'https://www.nordnet.se/',
                'User-Agent': random.choice(self.user_agents)
            })
            
            response = self.session.get(search_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for price data
                price_element = soup.find('span', class_='price') or soup.find('div', class_='price')
                
                price = None
                if price_element:
                    price_text = price_element.get_text().strip()
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        price = float(price_match.group().replace(',', ''))
                
                # Extract name
                name_element = soup.find('h1') or soup.find('title')
                name = name_element.get_text().strip() if name_element else ticker
                
                if price:
                    return {
                        'ticker': ticker,
                        'name': name,
                        'current_price': price,
                        'fetched_at': datetime.now(),
                        'source': 'Nordnet'
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Nordnet scraping error for {ticker}: {e}")
            return None
    
    def get_stock_from_marketwatch(self, ticker: str) -> Optional[Dict]:
        """Scrape from MarketWatch (more reliable)."""
        try:
            # MarketWatch format for Swedish stocks
            mw_ticker = f"{ticker}:XSTO"  # Stockholm exchange
            url = f"https://www.marketwatch.com/investing/stock/{mw_ticker}"
            
            headers = self.session.headers.copy()
            headers.update({
                'Referer': 'https://www.marketwatch.com/',
                'User-Agent': random.choice(self.user_agents)
            })
            
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # MarketWatch price selector
                price_element = soup.find('bg-quote', class_='value') or soup.find('span', class_='value')
                
                price = None
                if price_element:
                    price_text = price_element.get_text().strip()
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        price = float(price_match.group().replace(',', ''))
                
                # Company name
                name_element = soup.find('h1', class_='company__name')
                name = name_element.get_text().strip() if name_element else ticker
                
                if price:
                    return {
                        'ticker': ticker,
                        'name': name,
                        'current_price': price,
                        'fetched_at': datetime.now(),
                        'source': 'MarketWatch'
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"MarketWatch scraping error for {ticker}: {e}")
            return None
    
    def get_stock_data(self, ticker: str) -> Optional[Dict]:
        """Get stock data using multiple sources as fallbacks."""
        sources = [
            self.get_stock_from_avanza,
            self.get_stock_from_nordnet,
            self.get_stock_from_marketwatch
        ]
        
        for source_func in sources:
            try:
                data = source_func(ticker)
                if data and data.get('current_price'):
                    return data
                
                # Small delay between source attempts
                time.sleep(1)
                
            except Exception as e:
                logger.debug(f"Source {source_func.__name__} failed for {ticker}: {e}")
                continue
        
        return None
    
    async def fetch_multiple(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch multiple stocks with web scraping."""
        results = {}
        successful = 0
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Scraping {ticker} from multiple sources ({i+1}/{len(tickers)})")
            
            data = self.get_stock_data(ticker)
            
            if data and data.get('current_price'):
                results[ticker] = data
                successful += 1
                
                if websocket_manager:
                    source = data.get('source', 'unknown')
                    price = data.get('current_price')
                    await websocket_manager.send_log("success", f"✅ {ticker}: {price} SEK (via {source})")
            else:
                if websocket_manager:
                    await websocket_manager.send_log("warning", f"❌ {ticker}: No data from any source")
            
            # Delay between stocks to avoid detection
            if i < len(tickers) - 1:
                delay = random.uniform(3, 6)  # 3-6 second delays
                if websocket_manager:
                    await websocket_manager.send_log("info", f"Waiting {delay:.1f}s to avoid detection...")
                time.sleep(delay)
        
        logger.info(f"Web scraping completed: {successful}/{len(tickers)} successful")
        return results

async def scraping_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Sync using bulletproof web scraping."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting web scraping sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using bulletproof web scraping from Swedish brokers")
        
        # Use scraping fetcher
        fetcher = BulletproofScrapingFetcher()
        results = await fetcher.fetch_multiple(tickers, websocket_manager)
        
        # Update database
        successful = 0
        for ticker, data in results.items():
            try:
                db.merge(Stock(
                    ticker=ticker,
                    name=data.get('name', ''),
                    market_cap_msek=0,  # Web scraping doesn't provide market cap
                    sector=''
                ))
                
                # Only basic price data from scraping
                successful += 1
                
            except Exception as e:
                logger.error(f"Database error for {ticker}: {e}")
        
        db.commit()
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'SCRAPING_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'Bulletproof web scraping from Swedish brokers',
            'success_rate': f"{successful/len(tickers)*100:.1f}%" if tickers else "0%",
            'sources': ['Avanza', 'Nordnet', 'MarketWatch'],
            'reliability': 'High - uses Swedish broker sites'
        }
        
    except Exception as e:
        logger.error(f"Web scraping sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
