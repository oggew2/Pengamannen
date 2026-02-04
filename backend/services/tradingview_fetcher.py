"""
TradingView Scanner API fetcher for Swedish and Nordic stocks.
WARNING: Check ToS compliance before commercial use.
"""
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Nordic market configuration (fx_rate is fallback only - live rates fetched via get_fx_rates())
NORDIC_MARKETS = {
    'sweden': {'url': 'https://scanner.tradingview.com/sweden/scan', 'currency': 'SEK', 'fx_rate': 1.0},
    'finland': {'url': 'https://scanner.tradingview.com/finland/scan', 'currency': 'EUR', 'fx_rate': 11.4},
    'norway': {'url': 'https://scanner.tradingview.com/norway/scan', 'currency': 'NOK', 'fx_rate': 0.98},
    'denmark': {'url': 'https://scanner.tradingview.com/denmark/scan', 'currency': 'DKK', 'fx_rate': 1.53},
}

# Financial sectors to exclude (TradingView uses English names)
# Börslabbet excludes banks, insurance, etc. but KEEPS Investmentbolag for momentum
FINANCIAL_SECTORS_EXCLUDE = ['Finance']


class TradingViewFetcher:
    """Fetch fundamentals + momentum from TradingView Scanner API."""
    
    SCANNER_URL = "https://scanner.tradingview.com/sweden/scan"
    FINANCIAL_SECTORS = ["Finance"]
    
    COLUMNS = [
        "name", "description", "close", "change", "market_cap_basic", "sector", "type",
        "isin",  # ISIN for CSV import matching
        "price_earnings_ttm", "price_book_ratio", "price_sales_ratio",
        "price_free_cash_flow_ttm", "enterprise_value_ebitda_ttm",
        "net_income_ttm", "total_equity_fq", "total_assets_fq",
        "return_on_invested_capital", "free_cash_flow_ttm",
        "dividends_yield_current",  # Better match to Börslabbet (MAE 0.17 vs 0.36)
        "Perf.W", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
        "piotroski_f_score_ttm", "piotroski_f_score_fy",
        "net_income_fq", "cash_f_operating_activities_ttm",
        "total_debt_fq", "current_ratio_fq", "gross_margin_ttm",
        "total_shares_outstanding_fundamental", "total_revenue_ttm",
        "long_term_debt_fq",
        "net_income_yoy_growth_ttm", "total_debt_yoy_growth_fy",
        "gross_profit_yoy_growth_ttm", "total_revenue_yoy_growth_ttm",
        "total_assets_yoy_growth_fy",
        # For ROIC calculation: Net Income / (Debt + Equity - Cash)
        "cash_n_short_term_invest_fq",
        # For average equity (FCFROE improvement)
        "total_equity_fy",
        # For P/FCF fallback calculation (OCF - CapEx)
        "capital_expenditures_ttm",
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible)',
            'Content-Type': 'application/json',
        })
    
    def fetch_all(self, min_market_cap: float = 2e9) -> List[Dict]:
        """Fetch all Swedish stocks with market cap > threshold."""
        payload = {
            "filter": [
                {"left": "market_cap_basic", "operation": "greater", "right": min_market_cap},
            ],
            "markets": ["sweden"],
            "symbols": {"query": {"types": ["stock", "dr"]}},
            "columns": self.COLUMNS,
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "range": [0, 500]
        }
        
        try:
            response = self.session.post(self.SCANNER_URL, json=payload, timeout=30)
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            logger.error(f"TradingView fetch failed: {e}")
            return []
    
    def _parse_response(self, data: dict) -> List[Dict]:
        """Parse TradingView response into standardized format."""
        results = []
        
        for item in data.get('data', []):
            symbol = item.get('s', '')
            values = item.get('d', [])
            
            if len(values) != len(self.COLUMNS):
                continue
            
            row = dict(zip(self.COLUMNS, values))
            ticker = symbol.split(':')[-1] if ':' in symbol else symbol
            
            # Calculate ROE/ROA from TTM components
            roe = roa = None
            if row.get('net_income_ttm') and row.get('total_equity_fq'):
                roe = (row['net_income_ttm'] / row['total_equity_fq']) * 100
            if row.get('net_income_ttm') and row.get('total_assets_fq'):
                roa = (row['net_income_ttm'] / row['total_assets_fq']) * 100
            
            # FCFROE: use FCF/Equity, with OCF fallback when FCF is missing
            # OCF fallback improves coverage for ~10% of stocks (BIOA B, SNM, MYCR, NOTE)
            fcfroe = None
            equity = row.get('total_equity_fq')
            if equity and equity > 0:
                fcf = row.get('free_cash_flow_ttm')
                ocf = row.get('cash_f_operating_activities_ttm')
                if fcf is not None:
                    fcfroe = (fcf / equity) * 100
                elif ocf is not None:
                    # Use OCF as fallback (less accurate but better than missing)
                    fcfroe = (ocf / equity) * 100
            
            # Calculate ROIC: Net Income / (Debt + Equity - Cash) - matches Börslabbet
            # MAE 2.92pp vs 13.88pp for TradingView direct ROIC
            roic = None
            ni = row.get('net_income_ttm')
            debt = row.get('total_debt_fq') or 0
            equity = row.get('total_equity_fq') or 0
            cash = row.get('cash_n_short_term_invest_fq') or 0
            invested_capital = debt + equity - cash
            if ni and invested_capital > 0:
                roic = (ni / invested_capital) * 100
            
            f_score = (
                row.get('piotroski_f_score_ttm') or 
                row.get('piotroski_f_score_fy') or
                self._calculate_fscore(row)
            )
            
            # Calculate P/FCF with fallback: use TV value, or calculate from OCF - CapEx
            p_fcf = row.get('price_free_cash_flow_ttm')
            if p_fcf is None:
                ocf = row.get('cash_f_operating_activities_ttm')
                capex = row.get('capital_expenditures_ttm')
                mcap = row.get('market_cap_basic')
                if ocf is not None and capex is not None and mcap is not None:
                    fcf_calc = ocf + capex  # CapEx is negative
                    if fcf_calc > 0:
                        p_fcf = mcap / fcf_calc
            
            results.append({
                'ticker': ticker,
                'db_ticker': ticker.replace('_', ' '),  # Space format to match stocks table
                'name': row.get('description') or row.get('name'),
                'isin': row.get('isin'),  # ISIN for CSV import matching
                'close': row.get('close'),  # Current price
                'change_1d': row.get('change'),  # Daily change %
                'change_1w': row.get('Perf.W'),  # Weekly change %
                'change_1m': row.get('Perf.1M'),  # Monthly change %
                'market_cap': row.get('market_cap_basic'),
                'sector': row.get('sector'),
                'stock_type': row.get('type'),
                'pe': row.get('price_earnings_ttm'),
                'pb': row.get('price_book_ratio'),
                'ps': row.get('price_sales_ratio'),
                'p_fcf': p_fcf,
                'ev_ebitda': row.get('enterprise_value_ebitda_ttm'),
                'roe': roe,
                'roa': roa,
                'roic': roic,
                'fcfroe': fcfroe,
                'dividend_yield': row.get('dividends_yield_current'),
                'perf_1m': row.get('Perf.1M'),
                'perf_3m': row.get('Perf.3M'),
                'perf_6m': row.get('Perf.6M'),
                'perf_12m': row.get('Perf.Y'),
                'piotroski_f_score': f_score,
                'net_income': row.get('net_income_fq'),
                'operating_cf': row.get('cash_f_operating_activities_ttm'),
                'total_assets': row.get('total_assets_fq'),
                'long_term_debt': row.get('long_term_debt_fq'),
                'current_ratio': row.get('current_ratio_fq'),
                'gross_margin': row.get('gross_margin_ttm'),
                'shares_outstanding': row.get('total_shares_outstanding_fundamental'),
                'data_source': 'tradingview',
                'fetched_date': datetime.now().date(),
            })
        
        return results
    
    def _calculate_fscore(self, row: dict) -> Optional[int]:
        """Calculate Piotroski F-Score from components when direct value unavailable."""
        score = 0
        
        if row.get('net_income_ttm') and row['net_income_ttm'] > 0:
            score += 1
        if row.get('cash_f_operating_activities_ttm') and row['cash_f_operating_activities_ttm'] > 0:
            score += 1
        if row.get('net_income_yoy_growth_ttm') and row['net_income_yoy_growth_ttm'] > 0:
            score += 1
        
        ocf = row.get('cash_f_operating_activities_ttm')
        ni = row.get('net_income_ttm')
        if ocf and ni and ocf > ni:
            score += 1
        
        if row.get('total_debt_yoy_growth_fy') and row['total_debt_yoy_growth_fy'] < 0:
            score += 1
        if row.get('current_ratio_fq') and row['current_ratio_fq'] > 1:
            score += 1
        
        score += 1  # No dilution assumed
        
        if row.get('gross_profit_yoy_growth_ttm') and row['gross_profit_yoy_growth_ttm'] > 0:
            score += 1
        
        rev_growth = row.get('total_revenue_yoy_growth_ttm')
        asset_growth = row.get('total_assets_yoy_growth_fy')
        if rev_growth and asset_growth and rev_growth > asset_growth:
            score += 1
        
        return score if score > 0 else None

    def fetch_nordic(self, markets: List[str] = None, min_market_cap_sek: float = 2e9) -> List[Dict]:
        """
        Fetch stocks from multiple Nordic markets with currency conversion.
        
        Args:
            markets: List of markets to fetch from (sweden, finland, norway, denmark)
            min_market_cap_sek: Minimum market cap in SEK (converted from local currency)
        
        Returns:
            List of stocks with market_cap_sek field added
        
        Raises:
            ValueError: If no valid markets specified
        """
        if markets is None:
            markets = ['sweden', 'finland', 'norway', 'denmark']
        
        # Validate markets
        valid_markets = [m for m in markets if m in NORDIC_MARKETS]
        if not valid_markets:
            raise ValueError(f"No valid markets specified. Valid options: {list(NORDIC_MARKETS.keys())}")
        
        # Get current FX rates and store on self for callers to access
        fx_rates = get_fx_rates()
        self._fx_rates = fx_rates
        
        all_stocks = []
        fetch_errors = []
        
        for market in valid_markets:
            config = NORDIC_MARKETS[market]
            fx_rate = fx_rates.get(config['currency'], config['fx_rate'])
            
            # Validate FX rate is positive
            if fx_rate <= 0:
                logger.error(f"Invalid FX rate for {market}: {fx_rate}")
                fetch_errors.append(market)
                continue
            
            # Calculate local currency threshold
            min_local = min_market_cap_sek / fx_rate
            
            try:
                stocks = self._fetch_market(market, config['url'], min_local)
            except Exception as e:
                logger.error(f"Failed to fetch {market}: {e}")
                fetch_errors.append(market)
                continue
            
            if not stocks:
                logger.warning(f"No stocks returned for {market}")
            
            # Add market info and convert market cap to SEK
            for stock in stocks:
                stock['market'] = market
                stock['currency'] = config['currency']
                stock['fx_rate'] = fx_rate
                if stock.get('market_cap') and stock['market_cap'] > 0:
                    stock['market_cap_sek'] = stock['market_cap'] * fx_rate
                else:
                    stock['market_cap_sek'] = 0
                # Convert price to SEK for allocation calculations
                if stock.get('close') and stock['close'] > 0:
                    stock['price_sek'] = stock['close'] * fx_rate
                else:
                    stock['price_sek'] = 0
            
            all_stocks.extend(stocks)
            logger.info(f"Fetched {len(stocks)} stocks from {market}")
        
        if fetch_errors:
            logger.warning(f"Failed to fetch from markets: {fetch_errors}")
        
        if not all_stocks:
            logger.error("No stocks fetched from any market")
            return []
        
        # Deduplicate dual-listed stocks (keep highest market cap listing)
        all_stocks = self._deduplicate_stocks(all_stocks)
        
        # Filter by SEK market cap threshold (double-check after conversion)
        all_stocks = [s for s in all_stocks if s.get('market_cap_sek', 0) >= min_market_cap_sek]
        
        logger.info(f"Total Nordic stocks after dedup and filtering: {len(all_stocks)}")
        return all_stocks

    def _fetch_market(self, market: str, url: str, min_market_cap: float, retries: int = 2) -> List[Dict]:
        """
        Fetch stocks from a single market with retry logic.
        
        Args:
            market: Market name
            url: TradingView scanner URL
            min_market_cap: Minimum market cap in local currency
            retries: Number of retry attempts on failure
        
        Returns:
            List of parsed stock data
        """
        payload = {
            "filter": [
                {"left": "market_cap_basic", "operation": "greater", "right": min_market_cap},
            ],
            "markets": [market],
            "symbols": {"query": {"types": ["stock", "dr"]}},
            "columns": self.COLUMNS,
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "range": [0, 500]
        }
        
        last_error = None
        for attempt in range(retries + 1):
            try:
                response = self.session.post(url, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # Validate response structure
                if 'data' not in data:
                    logger.warning(f"Unexpected response structure for {market}: {list(data.keys())}")
                    return []
                
                return self._parse_response(data)
                
            except requests.exceptions.Timeout:
                last_error = f"Timeout after 30s"
                logger.warning(f"Timeout fetching {market} (attempt {attempt + 1}/{retries + 1})")
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning(f"Request error for {market} (attempt {attempt + 1}/{retries + 1}): {e}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error fetching {market}: {e}")
                break  # Don't retry on unexpected errors
            
            # Wait before retry
            if attempt < retries:
                import time
                time.sleep(1)
        
        logger.error(f"Failed to fetch {market} after {retries + 1} attempts: {last_error}")
        return []

    def _deduplicate_stocks(self, stocks: List[Dict]) -> List[Dict]:
        """
        Remove dual-listed stocks and multiple share classes.
        
        Rules:
        1. Cross-listed stocks (same company on multiple exchanges): keep primary exchange
        2. Multiple share classes (A/B): keep B shares (higher liquidity in Nordics)
        
        Primary exchange priority: norway > sweden > finland > denmark for Norwegian companies,
        otherwise prefer the company's home market.
        """
        import re
        
        def normalize_name(name: str) -> str:
            """Normalize company name for matching."""
            name = name.lower().strip()
            # Remove common suffixes
            name = re.sub(r'\s+(ab|asa|oyj|a/s|ltd|plc|inc|corp|corporation|holding|group)\.?$', '', name)
            name = re.sub(r'\s+(class|ser\.?)\s*[ab]$', '', name)
            name = re.sub(r'\s+[ab]$', '', name)  # "SSAB B" -> "SSAB"
            return name.strip()
        
        def get_share_class(ticker: str, name: str) -> str:
            """Extract share class (A, B, or None)."""
            # Check ticker first (SSAB_A, SSAB_B)
            if ticker.endswith('_A') or ticker.endswith('-A'):
                return 'A'
            if ticker.endswith('_B') or ticker.endswith('-B'):
                return 'B'
            # Check name
            name_upper = name.upper()
            if ' A' in name_upper[-3:] or 'CLASS A' in name_upper or 'SER. A' in name_upper:
                return 'A'
            if ' B' in name_upper[-3:] or 'CLASS B' in name_upper or 'SER. B' in name_upper:
                return 'B'
            return None
        
        def is_preferred(new_stock, existing_stock) -> bool:
            """Determine if new_stock should replace existing_stock."""
            new_class = get_share_class(new_stock['ticker'], new_stock.get('name', ''))
            old_class = get_share_class(existing_stock['ticker'], existing_stock.get('name', ''))
            
            # Prefer B shares over A shares
            if new_class == 'B' and old_class == 'A':
                return True
            if new_class == 'A' and old_class == 'B':
                return False
            
            # For cross-listings, prefer primary exchange (where ticker doesn't end in 'O')
            # Swedish cross-listings of Norwegian stocks end in 'O' (e.g., AKERO for AKER)
            new_is_secondary = new_stock['ticker'].endswith('O') and new_stock['market'] == 'sweden'
            old_is_secondary = existing_stock['ticker'].endswith('O') and existing_stock['market'] == 'sweden'
            
            if old_is_secondary and not new_is_secondary:
                return True
            if new_is_secondary and not old_is_secondary:
                return False
            
            # Prefer higher market cap as tiebreaker
            return new_stock.get('market_cap_sek', 0) > existing_stock.get('market_cap_sek', 0)
        
        seen = {}  # normalized_name -> stock
        
        for stock in stocks:
            name = stock.get('name', '')
            norm_name = normalize_name(name)
            
            if norm_name in seen:
                if is_preferred(stock, seen[norm_name]):
                    seen[norm_name] = stock
            else:
                seen[norm_name] = stock
        
        return list(seen.values())


def get_fx_rates() -> Dict[str, float]:
    """
    Fetch current FX rates for Nordic currencies to SEK.
    Falls back to hardcoded rates if API fails.
    
    Returns rates as: 1 local currency = X SEK
    """
    # Reasonable default rates (updated Feb 2026)
    default_rates = {'SEK': 1.0, 'EUR': 11.4, 'NOK': 0.98, 'DKK': 1.53}
    
    try:
        # Use exchangerate-api.com (free tier)
        response = requests.get(
            'https://api.exchangerate-api.com/v4/latest/SEK',
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            rates = data.get('rates', {})
            
            # Validate rates are reasonable (within 50% of defaults)
            fetched_rates = {
                'SEK': 1.0,
                'EUR': 1 / rates.get('EUR', 1/11.5),
                'NOK': 1 / rates.get('NOK', 1/0.92),
                'DKK': 1 / rates.get('DKK', 1/1.55),
            }
            
            # Sanity check: rates should be within reasonable bounds
            for currency, rate in fetched_rates.items():
                if currency == 'SEK':
                    continue
                default = default_rates[currency]
                if rate < default * 0.5 or rate > default * 2.0:
                    logger.warning(f"FX rate for {currency} seems off: {rate:.4f} (default: {default})")
                    return default_rates
            
            logger.info(f"FX rates fetched: EUR={fetched_rates['EUR']:.4f}, NOK={fetched_rates['NOK']:.4f}, DKK={fetched_rates['DKK']:.4f}")
            return fetched_rates
            
    except Exception as e:
        logger.warning(f"Failed to fetch FX rates, using defaults: {e}")
    
    return default_rates


def fetch_omxs30_performance() -> dict:
    """
    Fetch OMXS30 index current price and performance from TradingView.
    Use for real-time benchmark comparison (not historical backtesting).
    """
    import requests
    
    url = "https://scanner.tradingview.com/sweden/scan"
    payload = {
        "symbols": {"tickers": ["OMXSTO:OMXS30"]},
        "columns": ["name", "close", "change", "change_abs", 
                    "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y", "Perf.YTD"]
    }
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if data.get('data'):
            row = data['data'][0]['d']
            return {
                'name': 'OMXS30',
                'close': row[1],
                'change_pct': row[2],
                'change_abs': row[3],
                'perf_1m': row[4],
                'perf_3m': row[5],
                'perf_6m': row[6],
                'perf_12m': row[7],
                'perf_ytd': row[8],
            }
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to fetch OMXS30: {e}")
    
    return None
