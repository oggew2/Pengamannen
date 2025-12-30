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
        self.current_sync_generation = int(datetime.now().timestamp())
        self.calls_made = 0
    
    def get_historical_prices(self, stock_id: str, days: int = 400) -> Optional[pd.DataFrame]:
        """Get historical prices from Avanza API."""
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
                'resolution': 'day'  # Request daily data instead of hourly
            }
            
            response = self.session.get(url, params=params, timeout=15)
            self.calls_made += 1
            
            if response.status_code == 200:
                data = response.json()
                ohlc_data = data.get('ohlc', [])
                
                if ohlc_data:
                    # Convert to DataFrame
                    df = pd.DataFrame(ohlc_data)
                    
                    # Convert timestamp to date
                    df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    # Rename columns to match our format
                    df = df.rename(columns={
                        'close': 'close',
                        'totalVolumeTraded': 'volume'
                    })
                    
                    # Select relevant columns
                    df = df[['date', 'close', 'volume', 'open', 'high', 'low']].copy()
                    
                    logger.debug(f"Fetched {len(df)} historical price points for stock {stock_id}")
                    return df
                else:
                    logger.warning(f"No OHLC data in response for stock {stock_id}")
                    return None
            else:
                logger.warning(f"Historical price request failed for stock {stock_id}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching historical prices for stock {stock_id}: {e}")
            return None
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
    
    def get_stock_overview(self, stock_id: str) -> Optional[Dict]:
        """Get stock overview data from Avanza with smart caching."""
        try:
            endpoint = "stock_overview"
            params = {'stock_id': stock_id}
            
            # Check smart cache first (24 hour TTL with age indicators)
            cached_data = smart_cache.get(endpoint, params, include_stale=True)
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
                
                # Calculate missing nyckeltal
                market_cap = market_cap_data.get('value')
                operating_cash_flow = operating_cash_flow_data.get('value')
                pb_ratio = key_indicators.get('priceBookRatio')
                
                # P/FCF = Market Cap / Operating Cash Flow
                p_fcf = None
                if market_cap and operating_cash_flow and operating_cash_flow > 0:
                    p_fcf = market_cap / operating_cash_flow
                
                # FCFROE = Operating Cash Flow / Total Equity
                # Total Equity = Market Cap / P/B ratio
                fcfroe = None
                if operating_cash_flow and market_cap and pb_ratio and pb_ratio > 0:
                    total_equity = market_cap / pb_ratio
                    fcfroe = operating_cash_flow / total_equity
                
                result = {
                    'id': stock_id,
                    'name': data.get('name', ''),
                    'ticker': listing.get('tickerSymbol', ''),  # Use tickerSymbol
                    'isin': data.get('isin', ''),
                    'current_price': current_price,
                    'change_percent': None,  # Not directly available in this endpoint
                    'volume': None,  # Not available in this endpoint
                    'market_cap': market_cap,
                    'pe': key_indicators.get('priceEarningsRatio'),
                    'pb': key_indicators.get('priceBookRatio'),
                    'ps': key_indicators.get('priceSalesRatio'),
                    'p_fcf': p_fcf,  # CALCULATED
                    'ev_ebitda': key_indicators.get('evEbitRatio'),
                    'dividend_yield': key_indicators.get('directYield'),
                    'roe': key_indicators.get('returnOnEquity'),
                    'roa': key_indicators.get('returnOnTotalAssets'),
                    'roic': key_indicators.get('returnOnCapitalEmployed'),
                    'fcfroe': fcfroe,  # CALCULATED
                    'sector': data.get('sectors', [{}])[0].get('sectorName') if data.get('sectors') else None,
                    'description': None,  # Not available in this endpoint
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
    
    def find_stock_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Find and get stock data by ticker using known mappings."""
        
        try:
            # Check if we have a known mapping
            stock_id = self.known_stocks.get(ticker)
            
            if stock_id:
                logger.debug(f"Using known mapping for {ticker} -> ID {stock_id}")
                return self.get_stock_overview(stock_id)
            
            # If no known mapping, try search (though it seems to be blocked)
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
        """Find and get stock data by ticker using known mappings."""
        
        try:
            # Check if we have a known mapping
            stock_id = self.known_stocks.get(ticker)
            
            if stock_id:
                logger.debug(f"Using known mapping for {ticker} -> ID {stock_id}")
                return self.get_stock_overview(stock_id)
            
            # If no known mapping, try search (though it seems to be blocked)
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
        """Get the known stock mappings."""
        return {
            "ERIC-B": "5240",  # Ericsson B
            "SWED-A": "5241",  # Swedbank A
            "INDU-A": "5244",  # Industrivärden A
            "INDU-C": "5245",  # Industrivärden C
            "INVE-A": "5246",  # Investor A
            "INVE-B": "5247",  # Investor B
            "NDA-SE": "5249",  # Nordea Bank
            "HOLM-A": "5250",  # Holmen A
            "HOLM-B": "5251",  # Holmen B
            "SEB-A": "5255",   # SEB A
            "SEB-C": "5256",   # SEB C
            "SKA-B": "5257",   # Skanska B
            "SKF-A": "5258",   # SKF A
            "SKF-B": "5259",   # SKF B
            "SSAB-A": "5260",  # SSAB A
            "SSAB-B": "5261",  # SSAB B
            "SCA-A": "5262",   # SCA A
            "SCA-B": "5263",   # SCA B
            "SHB-A": "5264",   # Handelsbanken A
            "SHB-B": "5265",   # Handelsbanken B
            "TREL-B": "5267",  # Trelleborg B
            "VOLV-A": "5268",  # Volvo A
            "VOLV-B": "5269",  # Volvo B
            "SECU-B": "5270",  # Securitas B
            "ASSA-B": "5271",  # Assa Abloy B
            "BEIJ-B": "5274",  # Beijer Ref B
            "BERG-B": "5275",  # Bergman & Beving B
        }
    
    async def fetch_multiple(self, tickers: List[str], websocket_manager=None) -> Dict[str, Dict]:
        """Fetch multiple Swedish stocks from Avanza."""
        results = {}
        successful = 0
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Avanza Direct: Fetching {len(tickers)} Swedish stocks")
        
        for i, ticker in enumerate(tickers):
            if websocket_manager:
                await websocket_manager.send_log("info", f"Searching Avanza for {ticker} ({i+1}/{len(tickers)})")
            
            data = self.find_stock_by_ticker(ticker)
            
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
            
            # Respectful delay
            if i < len(tickers) - 1:
                await asyncio.sleep(2)  # 2 second delay between requests
        
        # Cache stats
        cache_stats = self.cache.get_cache_stats()
        if websocket_manager:
            await websocket_manager.send_log("info", f"Avanza fetch complete: {successful}/{len(tickers)} successful")
            await websocket_manager.send_log("info", f"API calls: {self.calls_made}, Cache hits: {cache_stats['total_hits']}")
        
        logger.info(f"Avanza fetch: {successful}/{len(tickers)} successful, {self.calls_made} API calls")
        return results

async def avanza_sync(db, region: str = 'sweden', market_cap: str = 'large', websocket_manager=None) -> Dict:
    """Sync using Avanza Direct API."""
    from services.live_universe import get_live_stock_universe
    from models import Stock, Fundamentals
    
    start_time = datetime.now()
    
    try:
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Starting Avanza Direct sync: {len(tickers)} stocks")
        
        if websocket_manager:
            await websocket_manager.send_log("info", f"Using Avanza Direct API - FREE Swedish stock data")
        
        # Use Avanza Direct fetcher
        fetcher = AvanzaDirectFetcher()
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
                if any(data.get(field) for field in ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda', 'roe', 'roa', 'roic', 'fcfroe']):
                    db.merge(Fundamentals(
                        ticker=ticker,
                        fiscal_date=date.today(),
                        pe=data.get('pe'),
                        pb=data.get('pb'),
                        ps=data.get('ps'),
                        p_fcf=data.get('p_fcf'),  # Correct field name
                        ev_ebitda=data.get('ev_ebitda'),
                        dividend_yield=data.get('dividend_yield'),
                        roe=data.get('roe'),
                        roa=data.get('roa'),
                        roic=data.get('roic'),
                        fcfroe=data.get('fcfroe'),
                        fetched_date=date.today()
                    ))
                
                successful += 1
                
            except Exception as e:
                logger.error(f"Database error for {ticker}: {e}")
        
        db.commit()
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'status': 'AVANZA_DIRECT_COMPLETE',
            'processed': len(results),
            'successful': successful,
            'duration_seconds': duration,
            'method': 'Avanza Direct API - FREE Swedish stocks',
            'success_rate': f"{successful/len(tickers)*100:.1f}%" if tickers else "0%",
            'source': 'Avanza Direct',
            'cost': 'COMPLETELY FREE',
            'coverage': 'Swedish stocks with full fundamentals',
            'api_calls': fetcher.calls_made
        }
        
    except Exception as e:
        logger.error(f"Avanza Direct sync failed: {e}")
        return {'status': 'FAILED', 'error': str(e)}
