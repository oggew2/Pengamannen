"""
Test configuration and fixtures for Börslabbet App Test Suite.
"""
import pytest
import asyncio
import sys
import os

# Add backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
import tempfile

# Import main app and dependencies
from main import app
from db import get_db, Base
from models import Stock, DailyPrice, Fundamentals


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db():
    """Create a test database with shared connection for in-memory SQLite."""
    from sqlalchemy.pool import StaticPool
    
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    yield engine
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_db):
    """Create a test client with /v1 prefix."""
    base_client = TestClient(app)
    
    class V1Client:
        """Wrapper that prefixes all requests with /v1."""
        def __init__(self, client):
            self._client = client
        
        def get(self, url, **kwargs):
            return self._client.get(f"/v1{url}" if not url.startswith("/v1") else url, **kwargs)
        
        def post(self, url, **kwargs):
            return self._client.post(f"/v1{url}" if not url.startswith("/v1") else url, **kwargs)
        
        def put(self, url, **kwargs):
            return self._client.put(f"/v1{url}" if not url.startswith("/v1") else url, **kwargs)
        
        def delete(self, url, **kwargs):
            return self._client.delete(f"/v1{url}" if not url.startswith("/v1") else url, **kwargs)
        
        def patch(self, url, **kwargs):
            return self._client.patch(f"/v1{url}" if not url.startswith("/v1") else url, **kwargs)
    
    return V1Client(base_client)


@pytest.fixture
def auth_headers(test_db):
    """Create auth headers with a test user session."""
    from models import User, UserSession
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timedelta
    import uuid
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
    db = TestingSessionLocal()
    
    # Create test user with unique email
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=unique_email, password_hash="test", market_filter="both")
    db.add(user)
    db.commit()
    
    # Create session with expiry
    token = str(uuid.uuid4())
    session = UserSession(
        user_id=user.id, 
        token=token,
        expires_at=datetime.now() + timedelta(hours=24)
    )
    db.add(session)
    db.commit()
    db.close()
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def async_client(test_db):
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_stocks_data():
    """Sample stock data for testing."""
    return [
        {
            "ticker": "AAPL",
            "name": "Apple Inc",
            "market_cap": 3000000,  # 3B SEK
            "sector": "Technology",
            "exchange": "Stockholmsbörsen"
        },
        {
            "ticker": "MSFT", 
            "name": "Microsoft Corp",
            "market_cap": 2500000,  # 2.5B SEK
            "sector": "Technology",
            "exchange": "Stockholmsbörsen"
        },
        {
            "ticker": "GOOGL",
            "name": "Alphabet Inc",
            "market_cap": 2200000,  # 2.2B SEK
            "sector": "Technology", 
            "exchange": "First North"
        },
        {
            "ticker": "SMALL",
            "name": "Small Cap Stock",
            "market_cap": 1500000,  # 1.5B SEK - below 2B threshold
            "sector": "Industrials",
            "exchange": "Stockholmsbörsen"
        }
    ]


@pytest.fixture
def sample_fundamentals_data():
    """Sample fundamentals data for testing."""
    return [
        {
            "ticker": "AAPL",
            "pe_ratio": 25.5,
            "pb_ratio": 6.2,
            "ps_ratio": 7.1,
            "p_fcf": 22.3,
            "ev_ebitda": 18.9,
            "dividend_yield": 0.52,
            "roe": 0.175,
            "roa": 0.089,
            "roic": 0.156,
            "fcfroe": 0.142,
            "debt_to_equity": 1.73,
            "current_ratio": 0.94,
            "gross_margin": 0.382,
            "operating_margin": 0.297,
            "date": date.today()
        },
        {
            "ticker": "MSFT",
            "pe_ratio": 28.1,
            "pb_ratio": 12.8,
            "ps_ratio": 11.2,
            "p_fcf": 25.7,
            "ev_ebitda": 21.4,
            "dividend_yield": 0.72,
            "roe": 0.389,
            "roa": 0.156,
            "roic": 0.267,
            "fcfroe": 0.298,
            "debt_to_equity": 0.47,
            "current_ratio": 1.89,
            "gross_margin": 0.691,
            "operating_margin": 0.421,
            "date": date.today()
        },
        {
            "ticker": "GOOGL",
            "pe_ratio": 22.8,
            "pb_ratio": 5.1,
            "ps_ratio": 4.9,
            "p_fcf": 19.2,
            "ev_ebitda": 15.6,
            "dividend_yield": 0.0,
            "roe": 0.234,
            "roa": 0.134,
            "roic": 0.189,
            "fcfroe": 0.201,
            "debt_to_equity": 0.12,
            "current_ratio": 2.67,
            "gross_margin": 0.567,
            "operating_margin": 0.289,
            "date": date.today()
        }
    ]


@pytest.fixture
def sample_price_data():
    """Sample price data for momentum calculations."""
    base_date = date.today()
    prices = []
    
    for ticker in ["AAPL", "MSFT", "GOOGL"]:
        # Generate 300 days of price data
        for i in range(300):
            price_date = base_date - timedelta(days=i)
            # Simulate different momentum patterns
            if ticker == "AAPL":
                # Strong momentum
                base_price = 150 * (1 + 0.001 * (300 - i))
            elif ticker == "MSFT":
                # Moderate momentum
                base_price = 300 * (1 + 0.0005 * (300 - i))
            else:
                # Weak momentum
                base_price = 100 * (1 + 0.0002 * (300 - i))
            
            prices.append({
                "ticker": ticker,
                "date": price_date,
                "close": base_price + np.random.normal(0, base_price * 0.02),
                "volume": 1000000
            })
    
    return prices


@pytest.fixture
def strategy_test_data():
    """Complete test dataset for strategy calculations."""
    return {
        "stocks": [
            {"ticker": f"STOCK{i:02d}", "name": f"Test Stock {i}", 
             "market_cap": 2000 + i * 100, "sector": "Technology", 
             "exchange": "Stockholmsbörsen"} 
            for i in range(1, 21)  # 20 stocks above 2B threshold
        ],
        "fundamentals": [
            {
                "ticker": f"STOCK{i:02d}",
                "pe_ratio": 15 + i * 2,
                "pb_ratio": 1.5 + i * 0.5,
                "ps_ratio": 2.0 + i * 0.3,
                "p_fcf": 12 + i * 1.5,
                "ev_ebitda": 10 + i * 1.2,
                "dividend_yield": 0.02 + i * 0.001,
                "roe": 0.1 + i * 0.01,
                "roa": 0.05 + i * 0.005,
                "roic": 0.08 + i * 0.008,
                "fcfroe": 0.07 + i * 0.007,
                "date": date.today()
            }
            for i in range(1, 21)
        ]
    }


@pytest.fixture
def mock_avanza_response():
    """Mock Avanza API response."""
    return {
        "totalNumberOfHits": 1,
        "hits": [
            {
                "instrumentId": "5479",
                "name": "Test Stock",
                "ticker": "TEST",
                "marketCapital": 2500000000,
                "sector": "Technology",
                "marketPlace": "Stockholmsbörsen",
                "keyRatios": {
                    "priceEarningsRatio": 25.5,
                    "priceBookRatio": 6.2,
                    "priceSalesRatio": 7.1,
                    "returnOnEquity": 17.5,
                    "returnOnAssets": 8.9,
                    "dividendYield": 0.52
                },
                "quote": {
                    "last": 150.25,
                    "change": 2.15,
                    "changePercent": 1.45
                }
            }
        ]
    }


@pytest.fixture
def performance_thresholds():
    """Performance test thresholds."""
    return {
        "dashboard_load_time": 2.0,  # seconds
        "strategy_calculation_time": 5.0,  # seconds
        "api_response_time": 10.0,  # seconds
        "backtest_time": 30.0,  # seconds
        "cache_hit_ratio": 0.75,  # 75%
        "memory_usage_mb": 500  # MB
    }


@pytest.fixture
def go_no_go_checklist():
    """Go/No-Go release checklist items - comprehensive."""
    return {
        "critical_must_pass": [
            "all_4_strategies_return_10_stocks",
            "market_cap_filter_2b_sek",
            "avanza_api_integration_functional",
            "cache_system_24h_ttl",
            "data_freshness_indicators",
            "strategy_calculations_match_rules",
            "rebalancing_trades_mathematically_correct",
            "portfolio_import_export_functional",
            "performance_metrics_vs_omxs30",
            "all_19_pages_load_without_errors",
            "mobile_responsiveness",
            "docker_compose_deployment"
        ],
        "performance_gates": [
            "dashboard_loads_under_2s",
            "strategy_rankings_under_5s",
            "api_response_under_10s",
            "backtest_under_30s",
            "no_memory_leaks",
            "cache_efficiency_over_75_percent"
        ],
        "security_gates": [
            "no_sql_injection_vulnerabilities",
            "no_xss_vulnerabilities",
            "auth_endpoints_protected",
            "rate_limiting_enabled",
            "no_secrets_in_responses",
            "error_messages_not_revealing"
        ],
        "data_quality_gates": [
            "no_missing_fundamental_data",
            "sufficient_historical_price_data",
            "backtest_results_reproducible",
            "cost_calculations_accurate",
            "universe_constraints_enforced",
            "data_consistency_verified"
        ],
        "accessibility_gates": [
            "api_responses_screen_reader_friendly",
            "error_messages_descriptive",
            "data_structures_accessible"
        ],
        "reliability_gates": [
            "concurrent_requests_handled",
            "graceful_degradation_on_errors",
            "idempotent_operations"
        ]
    }


@pytest.fixture
def edge_case_stocks():
    """Stocks at market cap threshold boundaries."""
    return [
        {"ticker": "BELOW_2B", "name": "Below Threshold", "market_cap": 1999, "sector": "Tech", "exchange": "Stockholmsbörsen"},
        {"ticker": "EXACTLY_2B", "name": "At Threshold", "market_cap": 2000, "sector": "Tech", "exchange": "Stockholmsbörsen"},
        {"ticker": "ABOVE_2B", "name": "Above Threshold", "market_cap": 2001, "sector": "Tech", "exchange": "Stockholmsbörsen"}
    ]


@pytest.fixture
def large_portfolio_data():
    """Large portfolio for stress testing."""
    return {
        "holdings": [
            {"ticker": f"STOCK{i:03d}", "shares": 100, "avg_price": 100.0}
            for i in range(200)
        ],
        "portfolio_value": 2000000
    }


@pytest.fixture
def avanza_csv_sample():
    """Sample Avanza CSV for import testing."""
    return """Konto;Typ av transaktion;Värdepapper/beskrivning;ISIN;Datum;Antal;Kurs;Belopp;Valuta;Courtage;Valutakurs
Kapitalförsäkring;Köp;Apple Inc;US0378331005;2024-01-15;10;150,25;-1502,50;SEK;6,95;1,0000
Kapitalförsäkring;Köp;Microsoft Corp;US5949181045;2024-01-15;5;300,50;-1502,50;SEK;6,95;1,0000"""


@pytest.fixture
def backtest_golden_data():
    """Golden data for backtest verification."""
    return {
        "sammansatt_momentum": {
            "period": "2022-01-01 to 2023-12-31",
            "initial_capital": 100000,
            "expected_return_range": (0.10, 0.50),  # 10-50% return
            "expected_sharpe_range": (0.5, 1.5),
            "expected_max_drawdown_range": (-0.30, -0.05)
        }
    }
