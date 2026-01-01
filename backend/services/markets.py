"""Multi-market support - Nordic and US stock universes."""
from typing import List, Tuple, Dict

# Market configurations
MARKETS = {
    "sweden": {
        "name": "Sweden (OMX Stockholm)",
        "exchange_suffix": ".ST",
        "currency": "SEK",
        "benchmark": "^OMX",
        "timezone": "Europe/Stockholm"
    },
    "norway": {
        "name": "Norway (Oslo Børs)",
        "exchange_suffix": ".OL",
        "currency": "NOK",
        "benchmark": "^OSEAX",
        "timezone": "Europe/Oslo"
    },
    "denmark": {
        "name": "Denmark (Copenhagen)",
        "exchange_suffix": ".CO",
        "currency": "DKK",
        "benchmark": "^OMXC25",
        "timezone": "Europe/Copenhagen"
    },
    "finland": {
        "name": "Finland (Helsinki)",
        "exchange_suffix": ".HE",
        "currency": "EUR",
        "benchmark": "^OMXH25",
        "timezone": "Europe/Helsinki"
    },
    "us": {
        "name": "United States (NYSE/NASDAQ)",
        "exchange_suffix": "",
        "currency": "USD",
        "benchmark": "^GSPC",
        "timezone": "America/New_York"
    }
}


def get_nordic_stocks() -> List[Tuple[str, str]]:
    """Get list of major Nordic stocks (Sweden, Norway, Denmark, Finland)."""
    # Top stocks from each Nordic market
    stocks = [
        # Sweden (already have these)
        ("VOLV-B.ST", "Volvo"),
        ("ERIC-B.ST", "Ericsson"),
        ("ATCO-A.ST", "Atlas Copco"),
        ("INVE-B.ST", "Investor"),
        ("SEB-A.ST", "SEB"),
        
        # Norway
        ("EQNR.OL", "Equinor"),
        ("DNB.OL", "DNB Bank"),
        ("TEL.OL", "Telenor"),
        ("MOWI.OL", "Mowi"),
        ("ORK.OL", "Orkla"),
        ("YAR.OL", "Yara"),
        ("SALM.OL", "SalMar"),
        ("AKRBP.OL", "Aker BP"),
        ("NHY.OL", "Norsk Hydro"),
        ("SUBC.OL", "Subsea 7"),
        
        # Denmark
        ("NOVO-B.CO", "Novo Nordisk"),
        ("MAERSK-B.CO", "Maersk"),
        ("DSV.CO", "DSV"),
        ("VWS.CO", "Vestas"),
        ("CARL-B.CO", "Carlsberg"),
        ("COLO-B.CO", "Coloplast"),
        ("ORSTED.CO", "Ørsted"),
        ("PNDORA.CO", "Pandora"),
        ("DEMANT.CO", "Demant"),
        ("GN.CO", "GN Store Nord"),
        
        # Finland
        ("NOKIA.HE", "Nokia"),
        ("FORTUM.HE", "Fortum"),
        ("NESTE.HE", "Neste"),
        ("UPM.HE", "UPM-Kymmene"),
        ("SAMPO.HE", "Sampo"),
        ("KNEBV.HE", "Kone"),
        ("STERV.HE", "Stora Enso"),
        ("ELISA.HE", "Elisa"),
        ("KESKOB.HE", "Kesko"),
        ("ORNBV.HE", "Orion"),
    ]
    return stocks


def get_us_stocks() -> List[Tuple[str, str]]:
    """Get list of major US stocks (S&P 500 subset)."""
    stocks = [
        # Technology
        ("AAPL", "Apple"),
        ("MSFT", "Microsoft"),
        ("GOOGL", "Alphabet"),
        ("AMZN", "Amazon"),
        ("NVDA", "NVIDIA"),
        ("META", "Meta"),
        ("TSLA", "Tesla"),
        ("AVGO", "Broadcom"),
        ("ORCL", "Oracle"),
        ("CRM", "Salesforce"),
        
        # Healthcare
        ("UNH", "UnitedHealth"),
        ("JNJ", "Johnson & Johnson"),
        ("LLY", "Eli Lilly"),
        ("PFE", "Pfizer"),
        ("ABBV", "AbbVie"),
        ("MRK", "Merck"),
        ("TMO", "Thermo Fisher"),
        
        # Financials
        ("JPM", "JPMorgan"),
        ("V", "Visa"),
        ("MA", "Mastercard"),
        ("BAC", "Bank of America"),
        ("WFC", "Wells Fargo"),
        ("GS", "Goldman Sachs"),
        
        # Consumer
        ("WMT", "Walmart"),
        ("PG", "Procter & Gamble"),
        ("KO", "Coca-Cola"),
        ("PEP", "PepsiCo"),
        ("COST", "Costco"),
        ("MCD", "McDonald's"),
        ("NKE", "Nike"),
        
        # Industrial
        ("CAT", "Caterpillar"),
        ("HON", "Honeywell"),
        ("UPS", "UPS"),
        ("BA", "Boeing"),
        ("GE", "GE Aerospace"),
        
        # Energy
        ("XOM", "Exxon Mobil"),
        ("CVX", "Chevron"),
        
        # Other
        ("BRK-B", "Berkshire Hathaway"),
        ("DIS", "Disney"),
    ]
    return stocks


def get_stocks_for_market(market: str) -> List[Tuple[str, str]]:
    """Get stock list for a specific market."""
    if market == "sweden":
        from services.live_universe import get_live_stock_universe
        tickers = get_live_stock_universe('sweden', 'large')
        return [(t, t) for t in tickers]
    elif market == "nordic":
        return get_nordic_stocks()
    elif market == "us":
        return get_us_stocks()
    else:
        return []


def get_available_markets() -> List[Dict]:
    """Get list of available markets."""
    return [
        {"id": k, **v, "stock_count": len(get_stocks_for_market(k))}
        for k in ["sweden", "nordic", "us"]
    ]


def get_market_config(market: str) -> Dict:
    """Get configuration for a market."""
    if market == "nordic":
        return {
            "name": "Nordic (Sweden, Norway, Denmark, Finland)",
            "currencies": ["SEK", "NOK", "DKK", "EUR"],
            "benchmark": "^OMXN40",
            "timezone": "Europe/Stockholm"
        }
    return MARKETS.get(market, MARKETS["sweden"])
