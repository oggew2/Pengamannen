"""
Ticker mapping between TradingView and database formats.
TradingView: VOLV_B, HM_B, SSAB_B
Database:    VOLV B, HM B, SSAB B (space format to match stocks table)
"""

def tv_to_db_ticker(tv_ticker: str) -> str:
    """Convert TradingView ticker to database format (space, not dash)."""
    return tv_ticker.replace('_', ' ')

def db_to_tv_ticker(db_ticker: str) -> str:
    """Convert database ticker to TradingView format."""
    return db_ticker.replace('-', '_').replace(' ', '_')

def is_financial_sector(sector: str) -> bool:
    """Check if sector is financial (for exclusion in strategies)."""
    if not sector:
        return False
    return sector.lower() in ['finance', 'financial services']
