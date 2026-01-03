"""
Avanza Direct API fetcher - Free Swedish stock data from Avanza's public API.
Uses direct API calls without requiring the AvanzaPy library.
"""
import requests
import time
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import logging
import asyncio
import pandas as pd
from services.smart_cache import smart_cache

logger = logging.getLogger(__name__)

class AvanzaDirectFetcher:
    """Direct Avanza API fetcher for Swedish stocks."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'sv-SE,sv;q=0.9,en;q=0.8',
            'Referer': 'https://www.avanza.se/',
            'Origin': 'https://www.avanza.se'
        })
        
        # Initialize smart caching
        self.cache = smart_cache
        self.current_sync_generation = int(datetime.now().timestamp())
        self.calls_made = 0
    
    def get_historical_prices(self, stock_id: str, days: int = 400) -> Optional[pd.DataFrame]:
        """Get historical prices from Avanza API (max ~1825 days per request)."""
        try:
            from datetime import datetime, timedelta
            import pandas as pd
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            url = f"https://www.avanza.se/_api/price-chart/stock/{stock_id}"
            params = {
                'from': start_date.strftime('%Y-%m-%d'),
                'to': end_date.strftime('%Y-%m-%d'),
                'resolution': 'day'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                ohlc_data = data.get('ohlc', [])
                
                if ohlc_data:
                    df = pd.DataFrame(ohlc_data)
                    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                    df = df.rename(columns={'close': 'close', 'totalVolumeTraded': 'volume'})
                    df = df[['date', 'close', 'volume', 'open', 'high', 'low']].copy()
                    return df
            else:
                logger.warning(f"Historical price request failed for stock {stock_id}: HTTP {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching historical prices for stock {stock_id}: {e}")
            return None

    def get_historical_prices_extended(self, stock_id: str, years: int = 10) -> Optional[pd.DataFrame]:
        """Get extended historical prices by stitching multiple requests (max 1825 days each)."""
        from datetime import datetime, timedelta
        import pandas as pd
        
        all_data = []
        chunk_days = 1800  # Safe limit per request
        end_date = datetime.now()
        
        for i in range(0, years * 365, chunk_days):
            chunk_end = end_date - timedelta(days=i)
            chunk_start = chunk_end - timedelta(days=chunk_days)
            
            url = f"https://www.avanza.se/_api/price-chart/stock/{stock_id}"
            params = {
                'from': chunk_start.strftime('%Y-%m-%d'),
                'to': chunk_end.strftime('%Y-%m-%d'),
                'resolution': 'day'
            }
            
            try:
                response = self.session.get(url, params=params, timeout=15)
                self.calls_made += 1
                
                if response.status_code == 200:
                    data = response.json()
                    ohlc_data = data.get('ohlc', [])
                    if ohlc_data:
                        all_data.extend(ohlc_data)
                        
                        # CRITICAL FIX: Prevent memory accumulation in long loops
                        if len(all_data) > 50000:  # Limit to 50k records max
                            logger.warning(f"Truncating historical data at 50k records for {stock_id}")
                            break
                else:
                    break  # No more data available
            except:
                break
        
        if not all_data:
            return None
        
        df = pd.DataFrame(all_data)
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.rename(columns={'close': 'close', 'totalVolumeTraded': 'volume'})
        df = df[['date', 'close', 'volume', 'open', 'high', 'low']].copy()
        df = df.drop_duplicates(subset=['date']).sort_values('date')
        
        logger.info(f"Fetched {len(df)} extended price points for stock {stock_id}")
        return df
        """Search for instruments using Avanza's search API."""
        try:
            url = "https://www.avanza.se/_api/search/global-search/global-search-template"
            params = {
                'query': query,
                'limit': 10
            }
            
            response = self.session.get(url, params=params, timeout=15)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for hit in data.get('hits', []):
                    if hit.get('instrumentType') == 'STOCK':
                        results.append({
                            'id': hit.get('id'),
                            'name': hit.get('name'),
                            'ticker': hit.get('ticker'),
                            'isin': hit.get('isin'),
                            'market': hit.get('market', {}).get('name', ''),
                            'country': hit.get('market', {}).get('country', ''),
                            'currency': hit.get('currency'),
                            'type': hit.get('instrumentType')
                        })
                
                return results
            else:
                logger.warning(f"Avanza search failed with status {response.status_code}")
                return []
            
        except Exception as e:
            logger.error(f"Avanza search error for {query}: {e}")
            return []
    
    def get_stock_overview(self, stock_id: str, force_refresh: bool = False) -> Optional[Dict]:
        """Get stock overview data from Avanza with smart caching.
        
        Args:
            stock_id: Avanza stock ID
            force_refresh: Bypass cache and fetch fresh data
        """
        try:
            endpoint = "stock_overview"
            params = {'stock_id': stock_id}
            
            # Check smart cache first (auto TTL based on endpoint)
            cached_data = smart_cache.get(endpoint, params, include_stale=True, force_refresh=force_refresh)
            if cached_data and not cached_data.get('_cache_metadata', {}).get('is_expired', False):
                # Add cache age info to response
                cache_meta = cached_data.get('_cache_metadata', {})
                cached_data['data_age'] = cache_meta.get('age_category', 'unknown')
                cached_data['cache_age_minutes'] = cache_meta.get('age_minutes', 0)
                cached_data['from_cache'] = True
                return cached_data
            
            url = f"https://www.avanza.se/_api/market-guide/stock/{stock_id}"
            
            response = self.session.get(url, timeout=15)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract key data from the actual API structure
                key_indicators = data.get('keyIndicators', {})
                listing = data.get('listing', {})
                market_cap_data = key_indicators.get('marketCapital', {})
                operating_cash_flow_data = key_indicators.get('operatingCashFlow', {})
                
                # Get current price from historical data (most recent)
                historical = data.get('historicalClosingPrices', {})
                current_price = historical.get('oneDay')  # Most recent closing price
                
                # Extract raw values
                market_cap = market_cap_data.get('value')
                operating_cash_flow = operating_cash_flow_data.get('value')
                pb_ratio = key_indicators.get('priceBookRatio')
                pe_ratio = key_indicators.get('priceEarningsRatio')
                eps = key_indicators.get('earningsPerShare', {}).get('value')
                dividend_amount = key_indicators.get('dividend', {}).get('amount')
                equity_per_share = key_indicators.get('equityPerShare', {}).get('value')
                
                # Calculate derived fields
                p_fcf = None
                if market_cap and operating_cash_flow and operating_cash_flow > 0:
                    p_fcf = market_cap / operating_cash_flow
                
                # Total Equity = Market Cap / P/B
                total_equity = None
                if market_cap and pb_ratio and pb_ratio > 0:
                    total_equity = market_cap / pb_ratio
                
                # FCFROE = Operating Cash Flow / Total Equity
                fcfroe = None
                if operating_cash_flow and total_equity and total_equity > 0:
                    fcfroe = operating_cash_flow / total_equity
                
                # Net Income ≈ Market Cap / P/E
                net_income = None
                if market_cap and pe_ratio and pe_ratio > 0:
                    net_income = market_cap / pe_ratio
                
                # Shares Outstanding = Market Cap / (Equity Per Share * P/B)
                shares_outstanding = None
                if market_cap and equity_per_share and pb_ratio and equity_per_share > 0 and pb_ratio > 0:
                    shares_outstanding = market_cap / (equity_per_share * pb_ratio)
                
                # Payout Ratio = Dividend / EPS
                payout_ratio = None
                if dividend_amount and eps and eps > 0:
                    payout_ratio = dividend_amount / eps
                
                # Piotroski F-Score components from Avanza
                gross_margin = key_indicators.get('grossMargin')
                asset_turnover = key_indicators.get('capitalTurnover')
                equity_ratio = key_indicators.get('equityRatio')
                
                result = {
                    'id': stock_id,
                    'name': data.get('name', ''),
                    'ticker': listing.get('tickerSymbol', ''),
                    'isin': data.get('isin', ''),
                    'current_price': current_price,
                    'change_percent': None,
                    'volume': None,
                    'market_cap': market_cap,
                    'pe': pe_ratio,
                    'pb': pb_ratio,
                    'ps': key_indicators.get('priceSalesRatio'),
                    'p_fcf': p_fcf,
                    'ev_ebitda': key_indicators.get('evEbitRatio'),
                    'dividend_yield': key_indicators.get('directYield'),
                    'roe': key_indicators.get('returnOnEquity'),
                    'roa': key_indicators.get('returnOnTotalAssets'),
                    'roic': key_indicators.get('returnOnCapitalEmployed'),
                    'fcfroe': fcfroe,
                    'payout_ratio': payout_ratio,
                    # Piotroski components
                    'net_income': net_income,
                    'operating_cf': operating_cash_flow,
                    'total_assets': total_equity / equity_ratio if total_equity and equity_ratio and equity_ratio > 0 else None,
                    'gross_margin': gross_margin,
                    'asset_turnover': asset_turnover,
                    'current_ratio': 1 / equity_ratio if equity_ratio and equity_ratio > 0 else None,
                    'shares_outstanding': shares_outstanding,
                    'sector': data.get('sectors', [{}])[0].get('sectorName') if data.get('sectors') else None,
                    'currency': listing.get('currency', 'SEK'),
                    'fetched_at': datetime.now().isoformat(),
                    'source': 'Avanza Direct API',
                    'last_updated': datetime.now().isoformat(),
                    'fetch_success': True,
                    'data_age': 'fresh',
                    'from_cache': False
                }
                
                # Cache for 24 hours (until next sync)
                smart_cache.set(
                    endpoint, 
                    params, 
                    result, 
                    ttl_hours=24,
                    sync_generation=self.current_sync_generation
                )
                
                return result
            else:
                # Cache failed attempts for 1 hour
                failed_result = {
                    'id': stock_id,
                    'fetch_success': False,
                    'error': f'HTTP {response.status_code}',
                    'last_updated': datetime.now().isoformat(),
                    'source': 'Avanza Direct API',
                    'data_age': 'failed'
                }
                smart_cache.set(endpoint, params, failed_result, ttl_hours=1)
                logger.warning(f"Avanza stock data failed for {stock_id} with status {response.status_code}")
                return None
            
        except Exception as e:
            # Cache failed attempts for 1 hour
            failed_result = {
                'id': stock_id,
                'fetch_success': False,
                'error': str(e),
                'last_updated': datetime.now().isoformat(),
                'source': 'Avanza Direct API',
                'data_age': 'failed'
            }
            smart_cache.set(endpoint, params, failed_result, ttl_hours=1)
            logger.error(f"Avanza stock data error for {stock_id}: {e}")
            return None
    
    def get_complete_stock_data(self, ticker: str, include_history: bool = True) -> Dict:
        """Get complete stock data including historical prices from Avanza."""
        
        # Get Avanza stock ID
        stock_id = self.known_stocks.get(ticker)
        if not stock_id:
            logger.warning(f"No Avanza mapping for {ticker}")
            return {}
        
        # Get fundamentals from Avanza
        fundamentals = self.get_stock_overview(stock_id)
        if not fundamentals:
            logger.warning(f"No fundamental data for {ticker}")
            return {}
        
        # Get historical prices if requested
        historical_prices = None
        if include_history:
            historical_prices = self.get_historical_prices(stock_id)
        
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
            
            # Store historical data for momentum calculations
            complete_data['historical_prices'] = historical_prices.to_dict('records')
        else:
            complete_data['price_history_available'] = False
        
        return complete_data
    
    def search_instrument(self, query: str) -> List[Dict]:
        """Search for instruments using Avanza's search API."""
        try:
            url = "https://www.avanza.se/_api/search/global-search/global-search-template"
            params = {
                'query': query,
                'limit': 10
            }
            
            response = self.session.get(url, params=params, timeout=15)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for hit in data.get('hits', []):
                    if hit.get('instrumentType') == 'STOCK':
                        results.append({
                            'id': hit.get('id'),
                            'name': hit.get('name'),
                            'ticker': hit.get('ticker'),
                            'isin': hit.get('isin'),
                            'market': hit.get('market', {}).get('name', ''),
                            'country': hit.get('market', {}).get('country', ''),
                            'currency': hit.get('currency'),
                            'type': hit.get('instrumentType')
                        })
                
                return results
            else:
                logger.warning(f"Avanza search failed with status {response.status_code}")
                return []
            
        except Exception as e:
            logger.error(f"Avanza search error for {query}: {e}")
            return []
    
    def find_stock_by_ticker(self, ticker: str, id_map: dict = None, force_refresh: bool = False) -> Optional[Dict]:
        """Find and get stock data by ticker using database or hardcoded mappings."""
        
        try:
            # Use provided map or fall back to known_stocks
            stock_id = None
            if id_map:
                stock_id = id_map.get(ticker)
            if not stock_id:
                stock_id = self.known_stocks.get(ticker)
            
            if stock_id:
                return self.get_stock_overview(stock_id, force_refresh=force_refresh)
            
            return None
            
        except Exception as e:
            logger.error(f"Avanza find stock error for {ticker}: {e}")
            return None
            search_results = self.search_instrument(ticker)
            
            if not search_results:
                # Try alternative search terms
                alt_searches = [
                    ticker.replace('-', ' '),  # VOLV-B -> VOLV B
                    ticker.split('-')[0] if '-' in ticker else ticker,  # VOLV-B -> VOLV
                    ticker.replace('-', '')  # VOLV-B -> VOLVB
                ]
                
                for alt_term in alt_searches:
                    search_results = self.search_instrument(alt_term)
                    if search_results:
                        break
            
            if not search_results:
                logger.debug(f"No search results for {ticker} and no known mapping")
                return None
            
            # Find best match
            best_match = None
            for stock in search_results:
                stock_ticker = stock.get('ticker', '')
                
                # Exact match
                if stock_ticker == ticker:
                    best_match = stock
                    break
                
                # Close match (handle dash variations)
                if (stock_ticker.replace('-', '') == ticker.replace('-', '') or
                    stock_ticker.replace(' ', '-') == ticker):
                    best_match = stock
                    break
            
            # If no exact match, use first Swedish stock
            if not best_match:
                for stock in search_results:
                    if stock.get('country') == 'SE':
                        best_match = stock
                        break
            
            # Fallback to first result
            if not best_match and search_results:
                best_match = search_results[0]
            
            if best_match:
                stock_id = best_match['id']
                logger.debug(f"Found {ticker} -> {best_match['ticker']} (ID: {stock_id})")
                return self.get_stock_overview(stock_id)
            
            return None
            
        except Exception as e:
            logger.error(f"Avanza find stock error for {ticker}: {e}")
            return None
    
    @property
    def known_stocks(self):
        """Get all known stock mappings - Stockholmsbörsen + ETFs."""
        return {**self.stockholmsborsen_stocks, **self.index_etfs}
    
    @property
    def index_etfs(self):
        """Index ETFs for benchmarking."""
        return {
            "XACT-OMXS30": "5510",
            "XACT-SVERIGE": "5649",
        }
    
    @property
    def stockholmsborsen_stocks(self):
        """Stockholmsbörsen (XSTO) - Large, Mid, Small Cap. Updated from scan 0-10000."""
        return {
            # From scan - 147 stocks found
            "ATCO-A": "5234", "ATCO-B": "5235", "ALIV-SDB": "5236", "ELUX-A": "5237",
            "ELUX-B": "5238", "ERIC-A": "5239", "ERIC-B": "5240", "SWED-A": "5241",
            "INDU-A": "5244", "INDU-C": "5245", "INVE-A": "5246", "INVE-B": "5247",
            "NDA-SE": "5249", "HOLM-A": "5250", "HOLM-B": "5251", "SEB-A": "5255",
            "SEB-C": "5256", "SKA-B": "5257", "SKF-A": "5258", "SKF-B": "5259",
            "SSAB-A": "5260", "SSAB-B": "5261", "SCA-A": "5262", "SCA-B": "5263",
            "SHB-A": "5264", "SHB-B": "5265", "TREL-B": "5267", "VOLV-A": "5268",
            "VOLV-B": "5269", "SECU-B": "5270", "ASSA-B": "5271", "BEIJ-B": "5274",
            "BERG-B": "5275", "BILI-A": "5276", "BURE": "5277", "CNCJO-B": "5279",
            "EKTA-B": "5280", "GETI-B": "5282", "HEXA-B": "5286", "HUFV-A": "5287",
            "HAKI-A": "5291", "HAKI-B": "5292", "NCC-A": "5293", "NCC-B": "5294",
            "FABG": "5300", "AFRY": "5301", "ORES": "5302", "BEIA-B": "5303",
            "ACTI": "5304", "BONG": "5307", "ELAN-B": "5311", "FAG": "5314",
            "KABE-B": "5319", "LATO-B": "5321", "NEWA-B": "5324", "NIBE-B": "5325",
            "NOLA-B": "5327", "OEM-B": "5329", "PEAB-B": "5330", "PROF-B": "5331",
            "RROS": "5332", "SVED-B": "5335", "SVOL-A": "5336", "SVOL-B": "5337",
            "SKIS-B": "5339", "VBG-B": "5342", "WALL-B": "5344", "BIOG-B": "5349",
            "CAST": "5353", "FPAR-A": "5357", "AZA": "5361", "HAV-B": "5362",
            "HEBA-B": "5363", "HM-B": "5364", "KINV-A": "5368", "KINV-B": "5369",
            "STWK": "5373", "ATRLJ-B": "5374", "LUND-B": "5375", "MVIR": "5380",
            "SAFETY-B": "5382", "TEL2-A": "5385", "TEL2-B": "5386", "PREV-B": "5394",
            "PRIC-B": "5395", "RATO-A": "5396", "RATO-B": "5397", "LAMM-B": "5399",
            "SAAB-B": "5401", "SINT": "5406", "SWEC-A": "5408", "SWEC-B": "5409",
            "RAY-B": "5410", "XANO-B": "5415", "ENEA": "5416", "SOF-B": "5418",
            "STE-A": "5421", "STE-R": "5422", "CTT": "5425", "SECT-B": "5426",
            "KNOW": "5428", "MEAB-B": "5429", "AZN": "5431", "IS": "5436",
            "MTG-A": "5437", "MTG-B": "5438", "NETI-B": "5440", "ANOD-B": "5442",
            "MSON-A": "5443", "MSON-B": "5444", "ABB": "5447", "PION-B": "5450",
            "NTEK-B": "5452", "PACT": "5453", "DURC-B": "5454", "TIETOS": "5455",
            "CLAS-B": "5457", "BALD-B": "5459", "AXFO": "5465", "MYCR": "5466",
            "FING-B": "5468", "SAND": "5471", "TRAC-B": "5472", "MEKO": "5474",
            "EPEN": "5478", "TELIA": "5479", "ANOT": "5480", "BETS-B": "5482",
            "PREC": "5490", "ENRO": "5491", "SGG": "5497", "SVIK": "5500",
            "JM": "5501", "BTS-B": "5503", "BINV": "5505", "VITR": "5508",
            "VIT-B": "5526", "STAR-B": "5528", "AQ": "5534", "LAGR-B": "5536",
            "ADDT-B": "5537", "BILL": "5556", "BOL": "5564", "ALFA": "5580",
            "INTRUM": "5583", "NOBI": "5586", "ORRON": "5698", "NOTE": "6331",
            "LUMI": "7010",
        }
    
    @property
    def first_north_stocks(self):
        """First North stocks - to be populated when IDs are found."""
        return {}
    
    def get_stocks_by_market(self, market: str = "both") -> dict:
        """Get stocks filtered by market."""
        if market == "stockholmsborsen":
            return self.stockholmsborsen_stocks
        elif market == "first_north":
            return self.first_north_stocks
        else:  # both
            return {**self.stockholmsborsen_stocks, **self.first_north_stocks}
    
    async def fetch_multiple(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch multiple Swedish stocks from Avanza."""
        results = {}
        successful = 0
        total = len(tickers)
        
        logger.info(f"Starting fetch: {total} stocks")
        
        for i, ticker in enumerate(tickers):
            data = self.find_stock_by_ticker(ticker)
            
            if data and data.get('current_price'):
                results[ticker] = data
                successful += 1
            
            # Progress every 25 stocks
            if (i + 1) % 25 == 0 or i == total - 1:
                logger.info(f"Sync progress: {i+1}/{total} ({successful} successful)")
            
            # Respectful delay
            if i < total - 1:
                await asyncio.sleep(0.5)  # Reduced to 0.5s - still respectful but faster
        
        logger.info(f"Fetch complete: {successful}/{total} successful, {self.calls_made} API calls")
        return results

    def fetch_multiple_threaded(self, tickers: List[str], max_workers: int = 5, force_refresh: bool = False) -> Dict[str, Dict]:
        """Fetch multiple stocks using thread pool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from services.live_universe import get_avanza_id_map
        
        # Load ID map ONCE before threading
        id_map = get_avanza_id_map()
        
        results = {}
        successful = 0
        total = len(tickers)
        
        logger.info(f"Starting threaded fetch: {total} stocks, {max_workers} threads, force_refresh={force_refresh}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.find_stock_by_ticker, t, id_map, force_refresh): t for t in tickers}
            
            for i, future in enumerate(as_completed(futures)):
                ticker = futures[future]
                try:
                    data = future.result()
                    if data and data.get('current_price'):
                        results[ticker] = data
                        successful += 1
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
                
                if (i + 1) % 50 == 0 or i == total - 1:
                    logger.info(f"Sync progress: {i+1}/{total} ({successful} successful)")
        
        logger.info(f"Fetch complete: {successful}/{total} successful")
        return results

def _sync_prices_threaded(db, tickers: list, fetcher, id_map: dict, days: int = 400) -> int:
    """Sync historical prices with threading."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from models import DailyPrice
    
    successful = 0
    
    def fetch_prices(ticker):
        avanza_id = id_map.get(ticker)
        if not avanza_id:
            return None
        df = fetcher.get_historical_prices(avanza_id, days=days)
        return (ticker, df) if df is not None and len(df) > 0 else None
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_prices, t): t for t in tickers}
        for future in as_completed(futures):
            result = future.result()
            if result:
                ticker, df = result
                
                # CRITICAL FIX: Replace iterrows() with vectorized operations
                for idx in range(len(df)):
                    row = df.iloc[idx]
                    try:
                        db.merge(DailyPrice(
                            ticker=ticker,
                            date=row['date'].date() if hasattr(row['date'], 'date') else row['date'],
                            open=row.get('open'), close=row['close'],
                            high=row.get('high'), low=row.get('low'),
                            volume=row.get('volume')
                        ))
                    except:
                        pass
                successful += 1
    db.commit()
    return successful


async def avanza_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None, tier: str = 'active') -> Dict:
    """Sync fundamentals and prices using Avanza Direct API.
    
    Args:
        tier: 'active' (default) - fast daily sync of ~700 active stocks
              'discovery' - full sync of ~7,800 stocks to find new ones
    """
    from services.live_universe import get_live_stock_universe, get_avanza_id_map
    from services.cache import invalidate_cache
    from models import Stock, Fundamentals, FundamentalsSnapshot
    
    start_time = datetime.now()
    today = date.today()
    
    try:
        smart_cache.clear_all()
        invalidate_cache()
        logger.info("Cleared all caches before sync")
        
        tickers = get_live_stock_universe(region, market_cap, tier=tier)
        id_map = get_avanza_id_map()
        logger.info(f"Starting Avanza sync: {len(tickers)} stocks (tier={tier})")
        
        fetcher = AvanzaDirectFetcher()
        results = fetcher.fetch_multiple_threaded(tickers, max_workers=10, force_refresh=True)
        
        # Check if we should save a snapshot (weekly - one per week for historical lookups)
        week_start = today - timedelta(days=today.weekday())
        existing_snapshot = db.query(FundamentalsSnapshot).filter(
            FundamentalsSnapshot.snapshot_date >= week_start
        ).first()
        save_snapshot = existing_snapshot is None
        
        # Track failures for alerting
        failed_tickers = []
        
        # Update fundamentals
        successful = 0
        for ticker, data in results.items():
            try:
                # Update stock - preserve avanza_id and market from existing record
                existing = db.query(Stock).filter(Stock.ticker == ticker).first()
                stock = Stock(
                    ticker=ticker,
                    name=data.get('name', ''),
                    market_cap_msek=data.get('market_cap', 0) / 1e6 if data.get('market_cap') else 0,
                    sector=data.get('sector', ''),
                    avanza_id=existing.avanza_id if existing else data.get('id'),
                    market=existing.market if existing else 'Stockholmsbörsen'
                )
                db.merge(stock)
                
                if any(data.get(f) for f in ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda', 'roe', 'roa', 'roic', 'fcfroe', 'market_cap']):
                    db.query(Fundamentals).filter(Fundamentals.ticker == ticker).delete()
                    db.add(Fundamentals(
                        ticker=ticker, fiscal_date=today, market_cap=data.get('market_cap'),
                        pe=data.get('pe'), pb=data.get('pb'), ps=data.get('ps'),
                        p_fcf=data.get('p_fcf'), ev_ebitda=data.get('ev_ebitda'),
                        dividend_yield=data.get('dividend_yield'), roe=data.get('roe'),
                        roa=data.get('roa'), roic=data.get('roic'), fcfroe=data.get('fcfroe'),
                        payout_ratio=data.get('payout_ratio'), net_income=data.get('net_income'),
                        operating_cf=data.get('operating_cf'), total_assets=data.get('total_assets'),
                        gross_margin=data.get('gross_margin'), asset_turnover=data.get('asset_turnover'),
                        current_ratio=data.get('current_ratio'), shares_outstanding=data.get('shares_outstanding'),
                        fetched_date=today
                    ))
                    
                    # Save weekly snapshot for historical backtesting
                    if save_snapshot:
                        db.add(FundamentalsSnapshot(
                            snapshot_date=today, ticker=ticker, market_cap=data.get('market_cap'),
                            pe=data.get('pe'), pb=data.get('pb'), ps=data.get('ps'),
                            p_fcf=data.get('p_fcf'), ev_ebitda=data.get('ev_ebitda'),
                            roe=data.get('roe'), roa=data.get('roa'), roic=data.get('roic'),
                            fcfroe=data.get('fcfroe'), dividend_yield=data.get('dividend_yield'),
                            payout_ratio=data.get('payout_ratio')
                        ))
                successful += 1
            except Exception as e:
                failed_tickers.append({"ticker": ticker, "error": str(e)})
                logger.error(f"Database error for {ticker}: {e}")
        
        db.commit()
        logger.info(f"Fundamentals: {successful}/{len(tickers)}" + (f" (snapshot saved)" if save_snapshot else ""))
        
        # Always sync prices (400 days for momentum calculations)
        logger.info("Syncing historical prices...")
        prices_synced = _sync_prices_threaded(db, tickers, fetcher, id_map, days=400)
        logger.info(f"Prices: {prices_synced} stocks")
        
        # Pre-compute rankings for all strategies
        logger.info("Computing strategy rankings...")
        from services.ranking_cache import compute_all_rankings
        rankings_result = compute_all_rankings(db)
        logger.info(f"Rankings: {rankings_result.get('total_rankings', 0)} computed")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Calculate failure stats
        failed_count = len(tickers) - successful
        failed_pct = (failed_count / len(tickers) * 100) if tickers else 0
        
        # Log sync result
        _log_sync_result(db, successful, failed_count, duration, failed_tickers)
        
        # Determine sync status
        if failed_pct > 20:
            status = 'PARTIAL_FAILURE'
            warning = f"WARNING: {failed_pct:.1f}% of stocks failed to sync"
        elif failed_count > 0:
            status = 'COMPLETE_WITH_WARNINGS'
            warning = f"{failed_count} stocks had sync issues"
        else:
            status = 'COMPLETE'
            warning = None
        
        return {
            'status': status,
            'warning': warning,
            'fundamentals_synced': successful,
            'fundamentals_failed': failed_count,
            'failed_tickers': failed_tickers[:20],  # First 20 failures
            'prices_synced': prices_synced,
            'rankings_computed': rankings_result.get('total_rankings', 0),
            'total_stocks': len(tickers),
            'duration_seconds': round(duration, 1),
            'api_calls': fetcher.calls_made,
            'snapshot_saved': save_snapshot
        }
        
    except Exception as e:
        logger.error(f"Avanza sync failed: {e}")
        _log_sync_result(db, 0, len(tickers) if 'tickers' in dir() else 0, 0, [], error=str(e))
        return {'status': 'FAILED', 'error': str(e)}


def _log_sync_result(db, successful: int, failed: int, duration: float, failed_tickers: list, error: str = None):
    """Log sync result to database for monitoring."""
    from models import SyncLog
    import json
    
    try:
        log = SyncLog(
            sync_type="full",
            success=error is None and failed == 0,
            duration_seconds=duration,
            stocks_updated=successful,
            error_message=error,
            details_json=json.dumps({
                "failed_stocks": failed_tickers,
                "failed_count": failed
            }) if failed_tickers else None
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to log sync result: {e}")


def sync_omxs30_index(db) -> dict:
    """
    Sync OMXS30 index historical prices from Avanza.
    Only fetches new data since last stored date (incremental).
    """
    from models import IndexPrice
    from datetime import datetime, timedelta
    
    OMXS30_AVANZA_ID = "19002"
    INDEX_ID = "OMXS30"
    
    # Check last stored date
    last_date = db.query(IndexPrice.date).filter(
        IndexPrice.index_id == INDEX_ID
    ).order_by(IndexPrice.date.desc()).first()
    
    if last_date:
        last_date = last_date[0]
        days_since = (datetime.now().date() - last_date).days
        if days_since <= 1:  # Already have yesterday or today
            return {"status": "UP_TO_DATE", "records": 0}
        days_to_fetch = days_since + 5  # Small overlap for safety
    else:
        days_to_fetch = 365 * 40  # Fetch all available history (~40 years)
    
    fetcher = AvanzaDirectFetcher()
    
    # Fetch index prices
    try:
        all_data = []
        chunk_days = min(1800, days_to_fetch)  # Don't fetch more than needed
        end_date = datetime.now()
        
        for i in range(0, days_to_fetch, chunk_days):
            chunk_end = end_date - timedelta(days=i)
            chunk_start = chunk_end - timedelta(days=chunk_days)
            
            url = f"https://www.avanza.se/_api/price-chart/stock/{OMXS30_AVANZA_ID}"
            params = {
                'from': chunk_start.strftime('%Y-%m-%d'),
                'to': chunk_end.strftime('%Y-%m-%d'),
                'resolution': 'day'
            }
            
            response = fetcher.session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                ohlc = data.get('ohlc', [])
                if ohlc:
                    all_data.extend(ohlc)
                else:
                    break
            else:
                break
            time.sleep(0.1)
        
        if not all_data:
            return {"status": "NO_DATA", "records": 0}
        
        # Deduplicate by date and store
        seen_dates = set()
        new_records = 0
        for row in all_data:
            price_date = datetime.fromtimestamp(row['timestamp'] / 1000).date()
            
            if price_date in seen_dates:
                continue
            seen_dates.add(price_date)
            
            # Use merge to handle duplicates
            db.merge(IndexPrice(
                index_id=INDEX_ID,
                date=price_date,
                close=row.get('close'),
                open=row.get('open'),
                high=row.get('high'),
                low=row.get('low')
            ))
            new_records += 1
        
        db.commit()
        
        total = db.query(IndexPrice).filter(IndexPrice.index_id == INDEX_ID).count()
        return {"status": "SUCCESS", "new_records": new_records, "total_records": total}
        
    except Exception as e:
        logger.error(f"OMXS30 sync failed: {e}")
        return {"status": "FAILED", "error": str(e)}
