"""Transaction cost calculator - broker fees, spread, and net returns."""
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class BrokerFees:
    """Swedish broker fee structures."""
    name: str
    min_fee: float  # SEK
    percentage: float  # As decimal (0.001 = 0.1%)
    max_fee: float = None  # SEK, None = no max


# Common Swedish brokers
BROKERS = {
    "avanza": BrokerFees("Avanza", min_fee=1, percentage=0.0015, max_fee=None),  # 0.15%, min 1 SEK
    "nordnet": BrokerFees("Nordnet", min_fee=39, percentage=0.0015, max_fee=None),  # 0.15%, min 39 SEK
    "degiro": BrokerFees("DEGIRO", min_fee=0, percentage=0.0005, max_fee=None),  # 0.05%
    "interactive_brokers": BrokerFees("Interactive Brokers", min_fee=0, percentage=0.0005, max_fee=None),
}

# Default spread estimates by market cap
SPREAD_ESTIMATES = {
    "large_cap": 0.001,   # 0.1% for large caps
    "mid_cap": 0.002,     # 0.2% for mid caps
    "small_cap": 0.005,   # 0.5% for small caps
}


def calculate_broker_fee(trade_value: float, broker: str = "avanza") -> float:
    """Calculate broker commission for a trade."""
    if trade_value <= 0:
        return 0.0
    
    if broker not in BROKERS:
        broker = "avanza"
    
    fees = BROKERS[broker]
    calculated = trade_value * fees.percentage
    
    if calculated < fees.min_fee:
        return fees.min_fee
    if fees.max_fee and calculated > fees.max_fee:
        return fees.max_fee
    return calculated


def calculate_spread_cost(trade_value: float, spread_pct: float = 0.002) -> float:
    """Calculate estimated spread cost (half spread for one-way trade)."""
    return trade_value * (spread_pct / 2)


def calculate_total_transaction_cost(
    trade_value: float,
    broker: str = "avanza",
    spread_pct: float = 0.002,
    is_round_trip: bool = False
) -> Dict:
    """
    Calculate total transaction costs.
    
    Args:
        trade_value: Value of the trade in SEK
        broker: Broker name
        spread_pct: Estimated bid-ask spread
        is_round_trip: If True, calculate for buy + sell
    """
    multiplier = 2 if is_round_trip else 1
    
    broker_fee = calculate_broker_fee(trade_value, broker) * multiplier
    spread_cost = calculate_spread_cost(trade_value, spread_pct) * multiplier
    total = broker_fee + spread_cost
    
    return {
        "trade_value": trade_value,
        "broker": broker,
        "broker_fee": round(broker_fee, 2),
        "spread_cost": round(spread_cost, 2),
        "total_cost": round(total, 2),
        "cost_pct": round(total / trade_value * 100, 3) if trade_value > 0 else 0,
        "is_round_trip": is_round_trip
    }


def calculate_rebalance_costs(
    trades: List[Dict],
    broker: str = "avanza",
    spread_pct: float = 0.002
) -> Dict:
    """
    Calculate total costs for a rebalance.
    
    Args:
        trades: List of {ticker, action, estimated_value}
    """
    total_broker_fees = 0
    total_spread_costs = 0
    total_trade_value = 0
    
    trade_details = []
    
    for trade in trades:
        value = trade.get("estimated_value", 0)
        if value <= 0:
            continue
        
        broker_fee = calculate_broker_fee(value, broker)
        spread_cost = calculate_spread_cost(value, spread_pct)
        
        total_broker_fees += broker_fee
        total_spread_costs += spread_cost
        total_trade_value += value
        
        trade_details.append({
            "ticker": trade.get("ticker"),
            "action": trade.get("action"),
            "value": value,
            "broker_fee": round(broker_fee, 2),
            "spread_cost": round(spread_cost, 2),
            "total_cost": round(broker_fee + spread_cost, 2)
        })
    
    total_costs = total_broker_fees + total_spread_costs
    
    return {
        "total_trade_value": round(total_trade_value, 2),
        "total_broker_fees": round(total_broker_fees, 2),
        "total_spread_costs": round(total_spread_costs, 2),
        "total_costs": round(total_costs, 2),
        "cost_pct": round(total_costs / total_trade_value * 100, 3) if total_trade_value > 0 else 0,
        "broker": broker,
        "trades": trade_details
    }


def calculate_annual_cost_impact(
    portfolio_value: float,
    rebalances_per_year: int,
    turnover_pct: float = 0.5,
    broker: str = "avanza",
    spread_pct: float = 0.002
) -> Dict:
    """
    Estimate annual transaction cost impact on returns.
    
    Args:
        portfolio_value: Total portfolio value
        rebalances_per_year: Number of rebalances (4 for quarterly, 12 for monthly)
        turnover_pct: Estimated portfolio turnover per rebalance (0.5 = 50%)
        broker: Broker name
        spread_pct: Estimated spread
    """
    trade_value_per_rebalance = portfolio_value * turnover_pct
    
    costs_per_rebalance = calculate_total_transaction_cost(
        trade_value_per_rebalance, broker, spread_pct, is_round_trip=True
    )
    
    annual_costs = costs_per_rebalance["total_cost"] * rebalances_per_year
    annual_cost_pct = annual_costs / portfolio_value * 100 if portfolio_value > 0 else 0
    
    return {
        "portfolio_value": portfolio_value,
        "rebalances_per_year": rebalances_per_year,
        "turnover_pct": turnover_pct,
        "cost_per_rebalance": round(costs_per_rebalance["total_cost"], 2),
        "annual_costs": round(annual_costs, 2),
        "annual_cost_pct": round(annual_cost_pct, 3),
        "broker": broker,
        "note": f"Estimated drag on returns: {annual_cost_pct:.2f}% per year"
    }


def get_available_brokers() -> List[Dict]:
    """Get list of available brokers with fee structures."""
    return [
        {
            "id": k,
            "name": v.name,
            "min_fee": v.min_fee,
            "percentage": v.percentage * 100,
            "max_fee": v.max_fee
        }
        for k, v in BROKERS.items()
    ]
