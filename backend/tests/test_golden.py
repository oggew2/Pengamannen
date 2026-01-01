"""Golden file tests for strategy rankings.

These tests compare current strategy outputs against saved baselines.
To update baselines, run: pytest tests/test_golden.py --update-golden
"""
import json
import pytest
from pathlib import Path
from services.ranking import (
    calculate_momentum_score, calculate_value_score,
    calculate_dividend_score, calculate_quality_score
)

GOLDEN_DIR = Path(__file__).parent / "golden"


def load_golden(name: str) -> dict:
    """Load golden file, return empty dict if not exists."""
    path = GOLDEN_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_golden(name: str, data: dict):
    """Save golden file."""
    GOLDEN_DIR.mkdir(exist_ok=True)
    path = GOLDEN_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2))


@pytest.fixture
def update_golden(request):
    """Fixture to check if --update-golden flag was passed."""
    return request.config.getoption("--update-golden", default=False)


def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", help="Update golden files")


class TestStrategyGolden:
    """Test strategy outputs against golden baselines."""
    
    def test_momentum_top10_stable(self, db_session, update_golden):
        """Verify momentum strategy top 10 is stable."""
        from db import get_db
        db = next(get_db())
        
        scores = calculate_momentum_score(db)
        top10 = scores.nlargest(10).index.tolist()
        
        golden = load_golden("momentum_top10")
        
        if update_golden or not golden:
            save_golden("momentum_top10", {"tickers": top10})
            pytest.skip("Golden file updated")
        
        # Allow some drift (7 of 10 should match)
        overlap = len(set(top10) & set(golden.get("tickers", [])))
        assert overlap >= 7, f"Only {overlap}/10 tickers match golden. Current: {top10}"
    
    def test_value_top10_stable(self, db_session, update_golden):
        """Verify value strategy top 10 is stable."""
        from db import get_db
        db = next(get_db())
        
        scores = calculate_value_score(db)
        top10 = scores.nlargest(10).index.tolist()
        
        golden = load_golden("value_top10")
        
        if update_golden or not golden:
            save_golden("value_top10", {"tickers": top10})
            pytest.skip("Golden file updated")
        
        overlap = len(set(top10) & set(golden.get("tickers", [])))
        assert overlap >= 7, f"Only {overlap}/10 tickers match golden. Current: {top10}"
