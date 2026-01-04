"""
TradingView Scanner API fetcher for Swedish stocks.
WARNING: Check ToS compliance before commercial use.
"""
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingViewFetcher:
    """Fetch fundamentals + momentum from TradingView Scanner API."""
    
    SCANNER_URL = "https://scanner.tradingview.com/sweden/scan"
    FINANCIAL_SECTORS = ["Finance"]
    
    COLUMNS = [
        "name", "description", "close", "market_cap_basic", "sector", "type",
        "price_earnings_ttm", "price_book_ratio", "price_sales_ratio",
        "price_free_cash_flow_ttm", "enterprise_value_ebitda_ttm",
        "net_income_ttm", "total_equity_fq", "total_assets_fq",
        "return_on_invested_capital", "free_cash_flow_ttm",
        "dividends_yield_current",  # Better match to Börslabbet (MAE 0.17 vs 0.36)
        "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
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
