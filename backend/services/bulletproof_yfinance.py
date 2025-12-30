"""
Bulletproof Yahoo Finance fetcher based on 2024 research.
Implements all known workarounds for 429 rate limiting.
"""
import yfinance as yf
import requests
import time
import random
import hashlib
from datetime import datetime, date
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class BulletproofYFinanceFetcher:
    """Bulletproof fetcher implementing all 2024 workarounds."""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Setup session with proper headers."""
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
    
    def _generate_unique_user_agent(self):
        """Generate unique user agent to avoid detection."""
        timestamp = str(int(time.time()))
        hash_suffix = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        base_agent = random.choice(self.user_agents)
        return f"{base_agent} Custom/{hash_suffix}"
    
    def _fetch_with_fallback(self, ticker: str, max_retries: int = 5) -> Dict:
        """Fetch with multiple fallback strategies."""
        yahoo_ticker = ticker if '.ST' in ticker else f"{ticker}.ST"
        clean_ticker = ticker.replace('.ST', '')
        
        for attempt in range(max_retries):
            try:
                # Strategy 1: Standard yfinance
                if attempt == 0:
                    stock = yf.Ticker(yahoo_ticker)
                    info = stock.info
                    
                    if info and len(info) > 5:
                        return self._extract_data(clean_ticker, info)
                
                # Strategy 2: Custom session with unique headers
                elif attempt == 1:
                    # Create fresh session with unique user agent
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': self._generate_unique_user_agent(),
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://finance.yahoo.com/',
                        'Origin': 'https://finance.yahoo.com'
                    })
                    
                    stock = yf.Ticker(yahoo_ticker, session=session)
                    info = stock.info
                    
                    if info and len(info) > 5:
                        return self._extract_data(clean_ticker, info)
                
                # Strategy 3: Direct API call with custom headers
                elif attempt == 2:
                    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{yahoo_ticker}"
                    params = {
                        'modules': 'financialData,defaultKeyStatistics,summaryDetail,quoteType',
                        'corsDomain': 'finance.yahoo.com'
                    }
                    
                    headers = {
                        'User-Agent': self._generate_unique_user_agent(),
                        'Referer': f'https://finance.yahoo.com/quote/{yahoo_ticker}',
                        'Accept': 'application/json'
                    }
                    
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'quoteSummary' in data and data['quoteSummary']['result']:
                            return self._extract_from_api(clean_ticker, data['quoteSummary']['result'][0])
                
                # Strategy 4: Longer delay + different endpoint
                elif attempt == 3:
                    time.sleep(random.uniform(5, 10))  # Longer delay
                    
                    # Try different endpoint
                    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}"
                    headers = {'User-Agent': self._generate_unique_user_agent()}
                    
                    response = requests.get(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if 'chart' in data and data['chart']['result']:
                            return self._extract_from_chart(clean_ticker, data['chart']['result'][0])
                
                # Strategy 5: Last resort with maximum delay
                else:
                    time.sleep(random.uniform(10, 15))
                    
                    # Try with completely fresh session
                    stock = yf.Ticker(yahoo_ticker)
                    try:
                        # Just get basic price info
                        hist = stock.history(period="1d")
                        if not hist.empty:
                            price = float(hist['Close'].iloc[-1])
                            return {
                                'ticker': clean_ticker,
                                'current_price': price,
                                'name': yahoo_ticker,
                                'fetched_at': datetime.now(),
                                'method': 'basic_price_only'
                            }
                    except:
                        pass
                
            except Exception as e:
                logger.debug(f"Attempt {attempt + 1} failed for {ticker}: {e}")
                
                # Progressive delay
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) + random.uniform(1, 3)
                    time.sleep(delay)
        
        logger.warning(f"All attempts failed for {ticker}")
        return {}
    
    def _extract_data(self, ticker: str, info: Dict) -> Dict:
        """Extract data from yfinance info."""
        return {
            'ticker': ticker,
            'name': info.get('longName', info.get('shortName', '')),
            'current_price': info.get('currentPrice') or info.get('regularMarketPrice'),
            'market_cap': info.get('marketCap', 0) / 1e6 if info.get('marketCap') else 0,
            'pe': info.get('trailingPE'),
            'pb': info.get('priceToBook'),
            'ps': info.get('priceToSalesTrailing12Months'),
            'ev_ebitda': info.get('enterpriseToEbitda'),
            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None,
            'sector': info.get('sector', ''),
            'fetched_at': datetime.now(),
            'method': 'yfinance_info'
        }
    
    def _extract_from_api(self, ticker: str, data: Dict) -> Dict:
        """Extract data from direct API response."""
        financial_data = data.get('financialData', {})
        summary_detail = data.get('summaryDetail', {})
        default_stats = data.get('defaultKeyStatistics', {})
        
        return {
            'ticker': ticker,
            'name': data.get('quoteType', {}).get('longName', ''),
            'current_price': summary_detail.get('regularMarketPrice', {}).get('raw'),
            'market_cap': summary_detail.get('marketCap', {}).get('raw', 0) / 1e6 if summary_detail.get('marketCap') else 0,
            'pe': summary_detail.get('trailingPE', {}).get('raw'),
            'pb': default_stats.get('priceToBook', {}).get('raw'),
            'dividend_yield': summary_detail.get('dividendYield', {}).get('raw', 0) * 100 if summary_detail.get('dividendYield') else 0,
            'fetched_at': datetime.now(),
            'method': 'direct_api'
        }
    
    def _extract_from_chart(self, ticker: str, data: Dict) -> Dict:
        """Extract basic data from chart endpoint."""
        meta = data.get('meta', {})
        
        return {
            'ticker': ticker,
            'name': meta.get('longName', ''),
            'current_price': meta.get('regularMarketPrice'),
            'fetched_at': datetime.now(),
            'method': 'chart_api'
        }
    
    async def bulletproof_fetch(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Bulletproof fetch with all workarounds."""
        results = {}
        successful = 0
        
        logger.info(f"Starting bulletproof fetch for {len(tickers)} stocks")
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Fetching {ticker} ({i+1}/{len(tickers)})")
            
            # Sequential processing with delays (no concurrency to avoid 429)
            data = self._fetch_with_fallback(ticker)
            
            if data and (data.get('current_price') or data.get('market_cap', 0) > 0):
                results[ticker.replace('.ST', '')] = data
                successful += 1
                
                if websocket_manager:
                    method = data.get('method', 'unknown')
                    await websocket_manager.send_log("success", f"✅ {ticker}: {data.get('name', '')[:30]} (via {method})")
            else:
                if websocket_manager:
                    await websocket_manager.send_log("warning", f"❌ {ticker}: No data after all attempts")
            
            # Mandatory delay between requests (key to avoiding 429)
            if i < len(tickers) - 1:
                delay = random.uniform(3, 6)  # 3-6 second delays
                if websocket_manager:
                    await websocket_manager.send_log("info", f"Waiting {delay:.1f}s before next request...")
                time.sleep(delay)
        
        logger.info(f"Bulletproof fetch completed: {successful}/{len(tickers)} successful")
        return results

async def bulletproof_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Bulletproof sync with all 2024 workarounds."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting bulletproof sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using bulletproof method with all 2024 workarounds")
        
        # Use bulletproof fetcher
        fetcher = BulletproofYFinanceFetcher()
        results = await fetcher.bulletproof_fetch(tickers, websocket_manager)
        
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
                
                db.merge(Fundamentals(
                    ticker=ticker,
                    fiscal_date=date.today(),
                    pe=data.get('pe'),
                    pb=data.get('pb'),
                    ps=data.get('ps'),
                    ev_ebitda=data.get('ev_ebitda'),
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
            'status': 'BULLETPROOF_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'Bulletproof: 5 fallback strategies, sequential processing',
            'success_rate': f"{successful/len(tickers)*100:.1f}%" if tickers else "0%",
            'workarounds_used': ['unique_user_agents', 'direct_api_calls', 'progressive_delays', 'multiple_endpoints']
        }
        
    except Exception as e:
        logger.error(f"Bulletproof sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
