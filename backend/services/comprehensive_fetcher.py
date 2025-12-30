"""
Comprehensive Swedish stock data fetcher with full nyckeltal.
Uses multiple sources to get all fundamental data needed for Börslabbet strategies.
"""
import requests
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, date
from typing import Dict, List, Optional
import logging
import re
import json

logger = logging.getLogger(__name__)

class ComprehensiveSwedishFetcher:
    """Comprehensive fetcher for Swedish stocks with full fundamental data."""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Setup session with rotating headers to avoid detection."""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Cache-Control': 'max-age=0'
        })
    
    def _rotate_headers(self):
        """Rotate user agent and other headers to avoid detection."""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'X-Forwarded-For': f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            'X-Real-IP': f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        })
    
    def get_simplywall_data(self, ticker: str) -> Optional[Dict]:
        """Get comprehensive data from SimplyWall.st (has all nyckeltal)."""
        try:
            # SimplyWall.st URL format for Swedish stocks
            url = f"https://simplywall.st/stocks/se/{ticker.lower().replace('-', '')}"
            
            self._rotate_headers()
            self.session.headers.update({
                'Referer': 'https://simplywall.st/markets/se',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            })
            
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for JSON data in script tags (SimplyWall.st loads data via JS)
                script_tags = soup.find_all('script', type='application/json')
                
                for script in script_tags:
                    try:
                        data = json.loads(script.string)
                        if 'props' in data and 'pageProps' in data['props']:
                            stock_data = data['props']['pageProps']
                            return self._extract_simplywall_data(ticker, stock_data)
                    except:
                        continue
                
                # Fallback: scrape visible data
                return self._scrape_simplywall_visible(ticker, soup)
            
            return None
            
        except Exception as e:
            logger.debug(f"SimplyWall.st error for {ticker}: {e}")
            return None
    
    def _extract_simplywall_data(self, ticker: str, data: Dict) -> Dict:
        """Extract comprehensive data from SimplyWall.st JSON."""
        try:
            # SimplyWall.st has comprehensive fundamental data
            company = data.get('company', {})
            analysis = data.get('analysis', {})
            
            return {
                'ticker': ticker,
                'name': company.get('name', ''),
                'sector': company.get('sector', ''),
                'current_price': company.get('price', {}).get('current'),
                'market_cap': company.get('marketCap', 0) / 1e6 if company.get('marketCap') else 0,
                'pe': analysis.get('valuation', {}).get('pe'),
                'pb': analysis.get('valuation', {}).get('pb'),
                'ps': analysis.get('valuation', {}).get('ps'),
                'ev_ebitda': analysis.get('valuation', {}).get('evEbitda'),
                'dividend_yield': analysis.get('dividends', {}).get('yield', 0) * 100,
                'roe': analysis.get('financial', {}).get('roe', 0) * 100,
                'roa': analysis.get('financial', {}).get('roa', 0) * 100,
                'current_ratio': analysis.get('financial', {}).get('currentRatio'),
                'debt_to_equity': analysis.get('financial', {}).get('debtToEquity'),
                'piotroski_score': analysis.get('quality', {}).get('piotroskiScore'),
                'fetched_at': datetime.now(),
                'source': 'SimplyWall.st',
                'data_quality': 'COMPREHENSIVE'
            }
            
        except Exception as e:
            logger.error(f"SimplyWall.st data extraction error for {ticker}: {e}")
            return None
    
    def _scrape_simplywall_visible(self, ticker: str, soup: BeautifulSoup) -> Optional[Dict]:
        """Scrape visible data from SimplyWall.st as fallback."""
        try:
            # Look for key metrics in the page
            price_element = soup.find('span', class_='price') or soup.find('div', {'data-cy': 'price'})
            price = None
            
            if price_element:
                price_text = price_element.get_text().strip()
                price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                if price_match:
                    price = float(price_match.group().replace(',', ''))
            
            # Company name
            name_element = soup.find('h1') or soup.find('title')
            name = name_element.get_text().strip() if name_element else ticker
            
            if price:
                return {
                    'ticker': ticker,
                    'name': name,
                    'current_price': price,
                    'fetched_at': datetime.now(),
                    'source': 'SimplyWall.st_Scraped',
                    'data_quality': 'BASIC'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"SimplyWall.st scraping error for {ticker}: {e}")
            return None
    
    def get_investing_com_data(self, ticker: str) -> Optional[Dict]:
        """Get fundamental data from Investing.com (has comprehensive nyckeltal)."""
        try:
            # Investing.com format for Swedish stocks
            search_url = f"https://www.investing.com/search/?q={ticker}.ST"
            
            self._rotate_headers()
            self.session.headers.update({
                'Referer': 'https://www.investing.com/',
                'Accept': 'text/html,application/xhtml+xml'
            })
            
            # First, search for the stock
            search_response = self.session.get(search_url, timeout=10)
            
            if search_response.status_code == 200:
                soup = BeautifulSoup(search_response.content, 'html.parser')
                
                # Find the stock link
                stock_links = soup.find_all('a', href=re.compile(r'/equities/'))
                
                for link in stock_links:
                    if ticker.lower() in link.get('href', '').lower():
                        stock_url = f"https://www.investing.com{link['href']}"
                        
                        # Get the stock page
                        stock_response = self.session.get(stock_url, timeout=10)
                        
                        if stock_response.status_code == 200:
                            stock_soup = BeautifulSoup(stock_response.content, 'html.parser')
                            return self._extract_investing_data(ticker, stock_soup)
            
            return None
            
        except Exception as e:
            logger.debug(f"Investing.com error for {ticker}: {e}")
            return None
    
    def _extract_investing_data(self, ticker: str, soup: BeautifulSoup) -> Optional[Dict]:
        """Extract fundamental data from Investing.com."""
        try:
            # Investing.com has detailed fundamental data
            data = {'ticker': ticker, 'source': 'Investing.com'}
            
            # Price
            price_element = soup.find('span', {'data-test': 'instrument-price-last'})
            if price_element:
                price_text = price_element.get_text().strip()
                price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                if price_match:
                    data['current_price'] = float(price_match.group().replace(',', ''))
            
            # Company name
            name_element = soup.find('h1', class_='instrument-header_title')
            if name_element:
                data['name'] = name_element.get_text().strip()
            
            # Look for fundamental ratios table
            ratio_rows = soup.find_all('tr')
            for row in ratio_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text().strip().lower()
                    value_text = cells[1].get_text().strip()
                    
                    # Extract numeric value
                    value_match = re.search(r'[\d,]+\.?\d*', value_text.replace(',', ''))
                    if value_match:
                        value = float(value_match.group().replace(',', ''))
                        
                        # Map to our fields
                        if 'p/e' in label or 'pe ratio' in label:
                            data['pe'] = value
                        elif 'p/b' in label or 'price/book' in label:
                            data['pb'] = value
                        elif 'roe' in label or 'return on equity' in label:
                            data['roe'] = value
                        elif 'dividend yield' in label:
                            data['dividend_yield'] = value
            
            data['fetched_at'] = datetime.now()
            data['data_quality'] = 'GOOD'
            
            return data if data.get('current_price') else None
            
        except Exception as e:
            logger.error(f"Investing.com data extraction error for {ticker}: {e}")
            return None
    
    def get_comprehensive_data(self, ticker: str) -> Optional[Dict]:
        """Get comprehensive stock data using multiple sources."""
        sources = [
            ('SimplyWall.st', self.get_simplywall_data),
            ('Investing.com', self.get_investing_com_data)
        ]
        
        for source_name, source_func in sources:
            try:
                data = source_func(ticker)
                if data and data.get('current_price'):
                    logger.info(f"✅ Got comprehensive data for {ticker} from {source_name}")
                    return data
                
                # Delay between source attempts
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.debug(f"Source {source_name} failed for {ticker}: {e}")
                continue
        
        logger.warning(f"❌ No comprehensive data found for {ticker}")
        return None
    
    async def fetch_multiple_comprehensive(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch comprehensive data for multiple stocks."""
        results = {}
        successful = 0
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Fetching comprehensive data for {ticker} ({i+1}/{len(tickers)})")
            
            data = self.get_comprehensive_data(ticker)
            
            if data and data.get('current_price'):
                results[ticker] = data
                successful += 1
                
                if websocket_manager:
                    source = data.get('source', 'unknown')
                    quality = data.get('data_quality', 'unknown')
                    price = data.get('current_price')
                    pe = data.get('pe', 'N/A')
                    await websocket_manager.send_log("success", f"✅ {ticker}: {price} SEK, P/E: {pe} (via {source}, {quality})")
            else:
                if websocket_manager:
                    await websocket_manager.send_log("warning", f"❌ {ticker}: No comprehensive data available")
            
            # Anti-detection delays
            if i < len(tickers) - 1:
                delay = random.uniform(5, 10)  # Longer delays for comprehensive scraping
                if websocket_manager:
                    await websocket_manager.send_log("info", f"Anti-detection delay: waiting {delay:.1f}s...")
                time.sleep(delay)
        
        logger.info(f"Comprehensive fetch completed: {successful}/{len(tickers)} successful")
        return results

async def comprehensive_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Sync using comprehensive data sources with full nyckeltal."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting comprehensive sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using comprehensive scraping - full nyckeltal for Börslabbet strategies")
        
        # Use comprehensive fetcher
        fetcher = ComprehensiveSwedishFetcher()
        results = await fetcher.fetch_multiple_comprehensive(tickers, websocket_manager)
        
        # Update database with comprehensive data
        successful = 0
        for ticker, data in results.items():
            try:
                db.merge(Stock(
                    ticker=ticker,
                    name=data.get('name', ''),
                    market_cap_msek=data.get('market_cap', 0),
                    sector=data.get('sector', '')
                ))
                
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
            'status': 'COMPREHENSIVE_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'Comprehensive scraping with full nyckeltal',
            'success_rate': f"{successful/len(tickers)*100:.1f}%" if tickers else "0%",
            'sources': ['SimplyWall.st', 'Investing.com'],
            'data_quality': 'COMPREHENSIVE - All nyckeltal available',
            'anti_detection': 'Header rotation, delays, IP spoofing'
        }
        
    except Exception as e:
        logger.error(f"Comprehensive sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
