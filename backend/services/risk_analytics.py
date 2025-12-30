"""Risk analytics service - rolling metrics, sector exposure, factor analysis."""
import numpy as np
import pandas as pd
from typing import Dict, List
from datetime import date


def calculate_rolling_sharpe(
    returns: List[float],
    window: int = 63,  # ~3 months
    risk_free_rate: float = 0.02
) -> List[float]:
    """Calculate rolling Sharpe ratio."""
    if len(returns) < window:
        return []
    
    rf_daily = risk_free_rate / 252
    returns = np.array(returns)
    
    rolling_sharpe = []
    for i in range(window, len(returns) + 1):
        window_returns = returns[i-window:i]
        excess = window_returns - rf_daily
        if np.std(excess) > 0:
            sharpe = np.mean(excess) / np.std(excess) * np.sqrt(252)
        else:
            sharpe = 0
        rolling_sharpe.append(round(sharpe, 3))
    
    return rolling_sharpe


def calculate_rolling_volatility(
    returns: List[float],
    window: int = 21  # ~1 month
) -> List[float]:
    """Calculate rolling annualized volatility."""
    if len(returns) < window:
        return []
    
    returns = np.array(returns)
    rolling_vol = []
    
    for i in range(window, len(returns) + 1):
        vol = np.std(returns[i-window:i]) * np.sqrt(252) * 100
        rolling_vol.append(round(vol, 2))
    
    return rolling_vol


def calculate_sector_exposure(holdings: List[Dict]) -> Dict:
    """
    Calculate sector exposure from holdings.
    
    Args:
        holdings: List of {ticker, weight, sector}
    """
    sector_weights = {}
    
    for h in holdings:
        sector = h.get("sector", "Unknown")
        weight = h.get("weight", 0)
        sector_weights[sector] = sector_weights.get(sector, 0) + weight
    
    # Sort by weight
    sorted_sectors = sorted(sector_weights.items(), key=lambda x: -x[1])
    
    return {
        "sectors": [{"sector": s, "weight": round(w * 100, 1)} for s, w in sorted_sectors],
        "concentration": {
            "top_sector_pct": round(sorted_sectors[0][1] * 100, 1) if sorted_sectors else 0,
            "top_3_sectors_pct": round(sum(w for _, w in sorted_sectors[:3]) * 100, 1) if sorted_sectors else 0,
            "num_sectors": len(sorted_sectors)
        }
    }


def calculate_drawdown_analysis(values: List[float]) -> Dict:
    """Detailed drawdown analysis."""
    if len(values) < 2:
        return {}
    
    values = np.array(values)
    peak = np.maximum.accumulate(values)
    drawdown = (values - peak) / peak
    
    # Find drawdown periods
    in_drawdown = drawdown < 0
    drawdown_periods = []
    start_idx = None
    
    for i, dd in enumerate(in_drawdown):
        if dd and start_idx is None:
            start_idx = i
        elif not dd and start_idx is not None:
            drawdown_periods.append({
                "start_idx": start_idx,
                "end_idx": i,
                "length": i - start_idx,
                "max_dd": round(np.min(drawdown[start_idx:i]) * 100, 2)
            })
            start_idx = None
    
    # Current drawdown if still in one
    if start_idx is not None:
        drawdown_periods.append({
            "start_idx": start_idx,
            "end_idx": len(values) - 1,
            "length": len(values) - start_idx,
            "max_dd": round(np.min(drawdown[start_idx:]) * 100, 2),
            "ongoing": True
        })
    
    # Sort by severity
    worst_drawdowns = sorted(drawdown_periods, key=lambda x: x["max_dd"])[:5]
    
    return {
        "current_drawdown_pct": round(drawdown[-1] * 100, 2),
        "max_drawdown_pct": round(np.min(drawdown) * 100, 2),
        "avg_drawdown_pct": round(np.mean(drawdown[drawdown < 0]) * 100, 2) if np.any(drawdown < 0) else 0,
        "time_in_drawdown_pct": round(np.sum(in_drawdown) / len(values) * 100, 1),
        "worst_drawdowns": worst_drawdowns,
        "num_drawdown_periods": len(drawdown_periods)
    }


def calculate_var_cvar(
    returns: List[float],
    confidence: float = 0.95
) -> Dict:
    """Calculate Value at Risk and Conditional VaR."""
    if len(returns) < 20:
        return {"var": 0, "cvar": 0}
    
    returns = np.array(returns)
    
    # Historical VaR
    var = np.percentile(returns, (1 - confidence) * 100)
    
    # CVaR (Expected Shortfall)
    cvar = np.mean(returns[returns <= var])
    
    return {
        "var_daily_pct": round(var * 100, 2),
        "cvar_daily_pct": round(cvar * 100, 2),
        "var_annual_pct": round(var * np.sqrt(252) * 100, 2),
        "confidence": confidence
    }


def calculate_risk_metrics(
    values: List[float],
    benchmark_values: List[float] = None,
    risk_free_rate: float = 0.02
) -> Dict:
    """Comprehensive risk metrics."""
    if len(values) < 2:
        return {"error": "Insufficient data"}
    
    values = np.array(values)
    returns = np.diff(values) / values[:-1]
    
    # Basic stats
    total_return = (values[-1] / values[0] - 1) * 100
    ann_return = ((values[-1] / values[0]) ** (252 / len(returns)) - 1) * 100
    ann_vol = np.std(returns) * np.sqrt(252) * 100
    
    # Sharpe
    rf_daily = risk_free_rate / 252
    sharpe = (np.mean(returns) - rf_daily) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    # Sortino (downside deviation)
    downside = returns[returns < 0]
    downside_std = np.std(downside) if len(downside) > 0 else np.std(returns)
    sortino = (np.mean(returns) - rf_daily) / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    # Calmar (return / max drawdown)
    peak = np.maximum.accumulate(values)
    max_dd = np.min((values - peak) / peak)
    calmar = ann_return / abs(max_dd * 100) if max_dd != 0 else 0
    
    result = {
        "total_return_pct": round(total_return, 2),
        "annualized_return_pct": round(ann_return, 2),
        "annualized_volatility_pct": round(ann_vol, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "calmar_ratio": round(calmar, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "var_cvar": calculate_var_cvar(returns),
        "positive_days_pct": round(np.sum(returns > 0) / len(returns) * 100, 1),
        "best_day_pct": round(np.max(returns) * 100, 2),
        "worst_day_pct": round(np.min(returns) * 100, 2),
        "avg_daily_return_pct": round(np.mean(returns) * 100, 3)
    }
    
    # Rolling metrics
    result["rolling_sharpe_3m"] = calculate_rolling_sharpe(returns.tolist(), 63)[-10:] if len(returns) > 63 else []
    result["rolling_volatility_1m"] = calculate_rolling_volatility(returns.tolist(), 21)[-10:] if len(returns) > 21 else []
    
    return result
