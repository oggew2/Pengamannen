"""
Test Data Strategy for Börslabbet App.

Defines synthetic and realistic test datasets for comprehensive testing.
"""
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Any
import random
import numpy as np


class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_user_profiles() -> List[Dict[str, Any]]:
        """Generate example user profiles (novice vs experienced)."""
        return [
            {
                "id": 1,
                "username": "novice_investor",
                "profile_type": "novice",
                "portfolio_value": 50000,
                "experience_years": 0,
                "risk_tolerance": "low",
                "preferred_strategy": "trendande_utdelning"
            },
            {
                "id": 2,
                "username": "experienced_investor",
                "profile_type": "experienced",
                "portfolio_value": 500000,
                "experience_years": 10,
                "risk_tolerance": "high",
                "preferred_strategy": "sammansatt_momentum"
            },
            {
                "id": 3,
                "username": "balanced_investor",
                "profile_type": "intermediate",
                "portfolio_value": 150000,
                "experience_years": 3,
                "risk_tolerance": "medium",
                "preferred_strategy": "trendande_varde"
            }
        ]
    
    @staticmethod
    def generate_portfolios_various_sizes() -> List[Dict[str, Any]]:
        """Generate portfolios of different sizes."""
        return [
            {
                "name": "empty_portfolio",
                "holdings": [],
                "total_value": 0
            },
            {
                "name": "small_portfolio",
                "holdings": [
                    {"ticker": "AAPL", "shares": 10, "avg_price": 150.0},
                    {"ticker": "MSFT", "shares": 5, "avg_price": 300.0}
                ],
                "total_value": 3000
            },
            {
                "name": "standard_portfolio",
                "holdings": [
                    {"ticker": f"STOCK{i:02d}", "shares": 100, "avg_price": 100.0}
                    for i in range(10)
                ],
                "total_value": 100000
            },
            {
                "name": "large_portfolio",
                "holdings": [
                    {"ticker": f"STOCK{i:03d}", "shares": 50, "avg_price": 200.0}
                    for i in range(50)
                ],
                "total_value": 500000
            },
            {
                "name": "very_large_portfolio",
                "holdings": [
                    {"ticker": f"STOCK{i:03d}", "shares": 25, "avg_price": 100.0}
                    for i in range(200)
                ],
                "total_value": 500000
            }
        ]
    
    @staticmethod
    def generate_edge_stocks() -> List[Dict[str, Any]]:
        """Generate stocks at market cap threshold boundaries."""
        return [
            {
                "ticker": "JUST_BELOW",
                "name": "Just Below Threshold AB",
                "market_cap": 1999,  # 1.999B SEK - just below 2B
                "sector": "Technology",
                "exchange": "Stockholmsbörsen",
                "should_be_excluded": True
            },
            {
                "ticker": "EXACTLY_AT",
                "name": "Exactly At Threshold AB",
                "market_cap": 2000,  # 2.0B SEK - exactly at threshold
                "sector": "Industrials",
                "exchange": "Stockholmsbörsen",
                "should_be_excluded": False
            },
            {
                "ticker": "JUST_ABOVE",
                "name": "Just Above Threshold AB",
                "market_cap": 2001,  # 2.001B SEK - just above 2B
                "sector": "Healthcare",
                "exchange": "First North",
                "should_be_excluded": False
            },
            {
                "ticker": "WELL_ABOVE",
                "name": "Well Above Threshold AB",
                "market_cap": 5000,  # 5B SEK - well above
                "sector": "Financials",
                "exchange": "Stockholmsbörsen",
                "should_be_excluded": False
            },
            {
                "ticker": "MEGA_CAP",
                "name": "Mega Cap AB",
                "market_cap": 100000,  # 100B SEK - mega cap
                "sector": "Technology",
                "exchange": "Stockholmsbörsen",
                "should_be_excluded": False
            }
        ]
    
    @staticmethod
    def generate_backtest_golden_data() -> Dict[str, Any]:
        """Generate golden file data for backtest verification."""
        return {
            "sammansatt_momentum": {
                "period": "2020-01-01 to 2023-12-31",
                "initial_capital": 100000,
                "expected_results": {
                    "total_return": 0.45,  # 45% return
                    "annual_return": 0.13,  # 13% CAGR
                    "sharpe_ratio": 0.85,
                    "max_drawdown": -0.25,
                    "num_trades": 48,  # 4 years * 4 quarters * 3 avg trades
                    "tolerance": 0.05  # 5% tolerance for floating point
                }
            },
            "trendande_varde": {
                "period": "2020-01-01 to 2023-12-31",
                "initial_capital": 100000,
                "expected_results": {
                    "total_return": 0.35,
                    "annual_return": 0.10,
                    "sharpe_ratio": 0.70,
                    "max_drawdown": -0.20,
                    "num_trades": 12,  # 4 years * 1 annual * 3 avg trades
                    "tolerance": 0.05
                }
            }
        }
    
    @staticmethod
    def generate_strategy_golden_outputs() -> Dict[str, List[str]]:
        """Generate expected strategy outputs for verification."""
        # These would be actual expected top 10 stocks for a given date
        # Used to verify strategy calculations are deterministic
        return {
            "sammansatt_momentum_2024_01": [
                "STOCK01", "STOCK02", "STOCK03", "STOCK04", "STOCK05",
                "STOCK06", "STOCK07", "STOCK08", "STOCK09", "STOCK10"
            ],
            "trendande_varde_2024_01": [
                "VALUE01", "VALUE02", "VALUE03", "VALUE04", "VALUE05",
                "VALUE06", "VALUE07", "VALUE08", "VALUE09", "VALUE10"
            ]
        }
    
    @staticmethod
    def generate_price_history(
        ticker: str,
        days: int = 365,
        start_price: float = 100.0,
        volatility: float = 0.02,
        trend: float = 0.0001
    ) -> List[Dict[str, Any]]:
        """Generate realistic price history for a stock."""
        prices = []
        current_price = start_price
        base_date = date.today()
        
        for i in range(days):
            price_date = base_date - timedelta(days=days - i - 1)
            
            # Random walk with trend
            daily_return = np.random.normal(trend, volatility)
            current_price *= (1 + daily_return)
            
            prices.append({
                "ticker": ticker,
                "date": price_date.isoformat(),
                "open": current_price * (1 + np.random.uniform(-0.01, 0.01)),
                "high": current_price * (1 + np.random.uniform(0, 0.02)),
                "low": current_price * (1 - np.random.uniform(0, 0.02)),
                "close": current_price,
                "volume": int(np.random.uniform(100000, 1000000))
            })
        
        return prices
    
    @staticmethod
    def generate_fundamentals_data(
        ticker: str,
        quality: str = "average"
    ) -> Dict[str, Any]:
        """Generate fundamental data for a stock."""
        
        quality_multipliers = {
            "excellent": {"pe": 0.8, "quality": 1.3},
            "good": {"pe": 0.9, "quality": 1.1},
            "average": {"pe": 1.0, "quality": 1.0},
            "poor": {"pe": 1.2, "quality": 0.8},
            "very_poor": {"pe": 1.5, "quality": 0.6}
        }
        
        mult = quality_multipliers.get(quality, quality_multipliers["average"])
        
        return {
            "ticker": ticker,
            "pe_ratio": 20 * mult["pe"] + np.random.uniform(-5, 5),
            "pb_ratio": 3 * mult["pe"] + np.random.uniform(-1, 1),
            "ps_ratio": 2 * mult["pe"] + np.random.uniform(-0.5, 0.5),
            "p_fcf": 15 * mult["pe"] + np.random.uniform(-3, 3),
            "ev_ebitda": 12 * mult["pe"] + np.random.uniform(-2, 2),
            "dividend_yield": 0.03 * mult["quality"],
            "roe": 0.15 * mult["quality"],
            "roa": 0.08 * mult["quality"],
            "roic": 0.12 * mult["quality"],
            "fcfroe": 0.10 * mult["quality"],
            "debt_to_equity": 0.5 / mult["quality"],
            "current_ratio": 1.5 * mult["quality"],
            "gross_margin": 0.40 * mult["quality"],
            "operating_margin": 0.15 * mult["quality"],
            "market_cap": 3000 + np.random.uniform(-500, 2000),
            "date": date.today().isoformat()
        }
    
    @staticmethod
    def generate_complete_test_universe(num_stocks: int = 50) -> Dict[str, Any]:
        """Generate a complete test universe with all required data."""
        stocks = []
        fundamentals = []
        prices = {}
        
        for i in range(num_stocks):
            ticker = f"TEST{i:03d}"
            
            # Vary quality across stocks
            qualities = ["excellent", "good", "average", "poor", "very_poor"]
            quality = qualities[i % len(qualities)]
            
            # Stock info
            stocks.append({
                "ticker": ticker,
                "name": f"Test Company {i} AB",
                "market_cap": 2000 + i * 100,  # All above 2B threshold
                "sector": ["Technology", "Healthcare", "Industrials", "Financials", "Consumer"][i % 5],
                "exchange": "Stockholmsbörsen" if i % 3 != 0 else "First North"
            })
            
            # Fundamentals
            fundamentals.append(TestDataGenerator.generate_fundamentals_data(ticker, quality))
            
            # Price history
            trend = 0.0002 if quality in ["excellent", "good"] else -0.0001
            prices[ticker] = TestDataGenerator.generate_price_history(
                ticker, 
                days=365, 
                start_price=100 + i * 10,
                trend=trend
            )
        
        return {
            "stocks": stocks,
            "fundamentals": fundamentals,
            "prices": prices
        }


class TestFixtures:
    """Pre-defined test fixtures for common scenarios."""
    
    @staticmethod
    def empty_portfolio_fixture() -> Dict[str, Any]:
        """Fixture for testing empty portfolio scenarios."""
        return {
            "holdings": [],
            "total_value": 0,
            "cash": 100000
        }
    
    @staticmethod
    def single_strategy_fixture() -> Dict[str, Any]:
        """Fixture for testing single strategy scenarios."""
        return {
            "strategies": [
                {"name": "sammansatt_momentum", "weight": 1.0}
            ]
        }
    
    @staticmethod
    def multi_strategy_fixture() -> Dict[str, Any]:
        """Fixture for testing multi-strategy scenarios."""
        return {
            "strategies": [
                {"name": "sammansatt_momentum", "weight": 0.4},
                {"name": "trendande_varde", "weight": 0.3},
                {"name": "trendande_utdelning", "weight": 0.2},
                {"name": "trendande_kvalitet", "weight": 0.1}
            ]
        }
    
    @staticmethod
    def rebalancing_scenario_fixture() -> Dict[str, Any]:
        """Fixture for testing rebalancing scenarios."""
        return {
            "current_holdings": [
                {"ticker": "OLD_STOCK_1", "shares": 100, "avg_price": 100.0},
                {"ticker": "OLD_STOCK_2", "shares": 50, "avg_price": 200.0},
                {"ticker": "KEEP_STOCK", "shares": 75, "avg_price": 150.0}
            ],
            "target_holdings": [
                {"ticker": "NEW_STOCK_1", "shares": 80, "price": 125.0},
                {"ticker": "NEW_STOCK_2", "shares": 60, "price": 166.67},
                {"ticker": "KEEP_STOCK", "shares": 75, "price": 160.0}
            ],
            "portfolio_value": 100000
        }
    
    @staticmethod
    def avanza_csv_fixture() -> str:
        """Fixture for testing Avanza CSV import."""
        return """Konto;Typ av transaktion;Värdepapper/beskrivning;ISIN;Datum;Antal;Kurs;Belopp;Valuta;Courtage;Valutakurs
Kapitalförsäkring;Köp;Apple Inc;US0378331005;2024-01-15;10;150,25;-1502,50;SEK;6,95;1,0000
Kapitalförsäkring;Köp;Microsoft Corp;US5949181045;2024-01-15;5;300,50;-1502,50;SEK;6,95;1,0000
Kapitalförsäkring;Köp;Alphabet Inc;US02079K3059;2024-01-15;8;125,75;-1006,00;SEK;6,95;1,0000
Kapitalförsäkring;Sälj;Tesla Inc;US88160R1014;2024-02-01;3;200,00;600,00;SEK;6,95;1,0000"""
    
    @staticmethod
    def invalid_csv_fixtures() -> List[Dict[str, Any]]:
        """Fixtures for testing invalid CSV handling."""
        return [
            {
                "name": "wrong_delimiter",
                "content": "col1,col2,col3\nval1,val2,val3",
                "expected_error": "Invalid format"
            },
            {
                "name": "missing_columns",
                "content": "Konto;Datum\nTest;2024-01-01",
                "expected_error": "Missing required columns"
            },
            {
                "name": "invalid_numbers",
                "content": "Konto;Antal;Kurs\nTest;abc;xyz",
                "expected_error": "Invalid numeric values"
            },
            {
                "name": "empty_file",
                "content": "",
                "expected_error": "Empty file"
            }
        ]


# Export test data for use in tests
TEST_DATA = {
    "users": TestDataGenerator.generate_user_profiles(),
    "portfolios": TestDataGenerator.generate_portfolios_various_sizes(),
    "edge_stocks": TestDataGenerator.generate_edge_stocks(),
    "backtest_golden": TestDataGenerator.generate_backtest_golden_data(),
    "strategy_golden": TestDataGenerator.generate_strategy_golden_outputs(),
    "complete_universe": TestDataGenerator.generate_complete_test_universe(50)
}

FIXTURES = {
    "empty_portfolio": TestFixtures.empty_portfolio_fixture(),
    "single_strategy": TestFixtures.single_strategy_fixture(),
    "multi_strategy": TestFixtures.multi_strategy_fixture(),
    "rebalancing": TestFixtures.rebalancing_scenario_fixture(),
    "avanza_csv": TestFixtures.avanza_csv_fixture(),
    "invalid_csvs": TestFixtures.invalid_csv_fixtures()
}
