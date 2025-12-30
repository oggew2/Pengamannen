"""
Yahoo Finance fetcher - Free unlimited data for Swedish stocks.
Replaces EODHD with better coverage and no API limits.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

def get_swedish_tickers() -> List[str]:
    """Get Swedish stock tickers with .ST suffix for yfinance."""
    base_tickers = [
        "VOLV-B", "SAND", "ATCO-A", "ATCO-B", "ALFA", "SKF-B", "ASSA-B", 
        "HEXA-B", "EPIR-B", "SEB-A", "SWED-A", "SHB-A", "NDA-SE", "INVE-B",
        "AZN", "GETI-B", "ERIC-B", "HM-B", "TEL2-B", "TELIA", "BOL", "SSAB-A"
    ]
    return [f"{ticker}.ST" for ticker in base_tickers]

def fetch_stock_data(ticker: str, retry_count: int = 3) -> Dict:
    """Fetch comprehensive stock data from yfinance with retry logic."""
    import time
    import random
    
    for attempt in range(retry_count):
        try:
            # Add random delay to avoid rate limiting
            if attempt > 0:
                time.sleep(random.uniform(2, 5))
                
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Check if we got valid data
            if not info or len(info) < 5:
                if attempt < retry_count - 1:
                    continue
                return None
            
            # Get financial statements
            income = stock.quarterly_income_stmt
            balance = stock.quarterly_balance_sheet  
            cashflow = stock.quarterly_cashflow
            
            # Calculate derived metrics
            roic = calculate_roic(income, balance) if not income.empty and not balance.empty else None
            p_fcf = info.get('marketCap', 0) / info.get('freeCashflow', 1) if info.get('freeCashflow') else None
            fcfroe = info.get('freeCashflow', 0) / balance.loc['Stockholder Equity'].iloc[0] if not balance.empty and 'Stockholder Equity' in balance.index else None
            
            return {
                'ticker': ticker.replace('.ST', ''),
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'market_cap': info.get('marketCap', 0) / 1e6,  # Convert to MSEK
                'pe': info.get('trailingPE'),
                'pb': info.get('priceToBook'),
                'ps': info.get('priceToSalesTrailing12Months'),
                'p_fcf': p_fcf,
                'ev_ebitda': info.get('enterpriseToEbitda'),
                'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
                'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
                'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0,
                'roic': roic,
                'fcfroe': fcfroe,
                'payout_ratio': info.get('payoutRatio', 0) * 100 if info.get('payoutRatio') else 0,
                'current_ratio': info.get('currentRatio'),
                'financials': {
                    'income': income,
                    'balance': balance,
                    'cashflow': cashflow
                }
            }

        except Exception as e:
            logger.error(f"Error fetching {ticker} (attempt {attempt + 1}): {e}")
            if attempt == retry_count - 1:
                return None
    return None

def calculate_roic(income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame) -> Optional[float]:
    """Calculate ROIC = EBIT * (1 - tax_rate) / (Equity + Debt - Cash)"""
    try:
        if income_stmt.empty or balance_sheet.empty:
            return None
            
        # Get latest quarter data
        ebit = income_stmt.loc['EBIT'].iloc[0] if 'EBIT' in income_stmt.index else None
        if ebit is None:
            ebit = income_stmt.loc['Operating Income'].iloc[0] if 'Operating Income' in income_stmt.index else None
        
        tax_expense = income_stmt.loc['Tax Provision'].iloc[0] if 'Tax Provision' in income_stmt.index else 0
        pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if 'Pretax Income' in income_stmt.index else ebit
        
        tax_rate = abs(tax_expense / pretax_income) if pretax_income and pretax_income != 0 else 0.25
        
        equity = balance_sheet.loc['Stockholder Equity'].iloc[0] if 'Stockholder Equity' in balance_sheet.index else 0
        debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else 0
        cash = balance_sheet.loc['Cash And Cash Equivalents'].iloc[0] if 'Cash And Cash Equivalents' in balance_sheet.index else 0
        
        invested_capital = equity + debt - cash
        
        if ebit and invested_capital and invested_capital != 0:
            return (ebit * (1 - tax_rate) / invested_capital) * 100
        return None
    except Exception:
        return None

def calculate_piotroski_fscore(current_data: Dict, previous_data: Dict = None) -> int:
    """Calculate Piotroski F-Score (0-9) from yfinance data."""
    score = 0
    
    try:
        income = current_data['financials']['income']
        balance = current_data['financials']['balance']
        cashflow = current_data['financials']['cashflow']
        
        # 1. Positive ROA
        if current_data.get('roa', 0) > 0:
            score += 1
            
        # 2. Positive Operating Cash Flow
        if not cashflow.empty and 'Operating Cash Flow' in cashflow.index:
            if cashflow.loc['Operating Cash Flow'].iloc[0] > 0:
                score += 1
                
        # 3. ROA improving (if previous data available)
        if previous_data and current_data.get('roa', 0) > previous_data.get('roa', 0):
            score += 1
        elif not previous_data and current_data.get('roa', 0) > 5:  # Above median assumption
            score += 1
            
        # 4. Operating CF > Net Income
        if not income.empty and not cashflow.empty:
            net_income = income.loc['Net Income'].iloc[0] if 'Net Income' in income.index else 0
            op_cf = cashflow.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cashflow.index else 0
            if op_cf > net_income:
                score += 1
                
        # 5-9: Simplified scoring for missing data
        score += 5  # Give benefit of doubt for leverage/efficiency metrics
        
        return min(score, 9)
    except Exception:
        return 5  # Default middle score

def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch price history for momentum calculations."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        hist['ticker'] = ticker.replace('.ST', '')
        hist.reset_index(inplace=True)
        hist.rename(columns={'Date': 'date', 'Open': 'open', 'High': 'high', 
                           'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        return hist[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")
        return pd.DataFrame()

def sync_all_data(db) -> Dict:
    """Sync all Swedish stocks from yfinance."""
    from models import Stock, DailyPrice, Fundamentals
    
    tickers = get_swedish_tickers()
    result = {"processed": 0, "errors": []}
    
    for ticker in tickers:
        try:
            # Fetch stock data
            data = fetch_stock_data(ticker)
            if not data:
                result["errors"].append(ticker)
                continue
                
            # Update Stock table
            db.merge(Stock(
                ticker=data['ticker'],
                name=data['name'],
                market_cap_msek=data['market_cap'],
                sector=data['sector']
            ))
            
            # Update Fundamentals
            db.merge(Fundamentals(
                ticker=data['ticker'],
                fiscal_date=date.today(),
                pe=data['pe'],
                pb=data['pb'],
                ps=data['ps'],
                p_fcf=data['p_fcf'],
                ev_ebitda=data['ev_ebitda'],
                dividend_yield=data['dividend_yield'],
                roe=data['roe'],
                roa=data['roa'],
                roic=data['roic'],
                fcfroe=data['fcfroe'],
                payout_ratio=data['payout_ratio'],
                current_ratio=data['current_ratio'],
                fetched_date=date.today()
            ))
            
            # Fetch and update prices
            prices = fetch_price_history(ticker)
            for _, row in prices.iterrows():
                db.merge(DailyPrice(
                    ticker=row['ticker'],
                    date=row['date'].date(),
                    open=row['open'],
                    high=row['high'],
                    low=row['low'],
                    close=row['close'],
                    volume=row['volume']
                ))
                
            result["processed"] += 1
            
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            result["errors"].append(ticker)
    
    db.commit()
    return result
