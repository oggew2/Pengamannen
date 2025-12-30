"""CSV export service for rankings and backtest results."""
import csv
import io
from datetime import date
from typing import List, Dict, Any


def export_rankings_to_csv(rankings: List[Dict[str, Any]], strategy_name: str) -> str:
    """Export strategy rankings to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['Rank', 'Ticker', 'Score', 'Strategy', 'Date'])
    
    # Data
    for r in rankings:
        writer.writerow([
            r.get('rank', ''),
            r.get('ticker', ''),
            f"{r.get('score', 0):.4f}" if r.get('score') else '',
            strategy_name,
            date.today().isoformat()
        ])
    
    return output.getvalue()


def export_backtest_to_csv(result: Dict[str, Any]) -> str:
    """Export backtest results to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Summary section
    writer.writerow(['=== Backtest Summary ==='])
    writer.writerow(['Strategy', result.get('strategy_name', '')])
    writer.writerow(['Period', f"{result.get('start_date', '')} to {result.get('end_date', '')}"])
    writer.writerow(['Initial Capital', result.get('initial_capital', 100000)])
    writer.writerow(['Final Value', f"{result.get('final_value', 0):.2f}"])
    writer.writerow(['Total Return %', f"{result.get('total_return_pct', 0):.2f}"])
    writer.writerow(['CAGR %', f"{result.get('cagr_pct', 0):.2f}"])
    writer.writerow(['Sharpe Ratio', f"{result.get('sharpe_ratio', 0):.2f}"])
    writer.writerow(['Sortino Ratio', f"{result.get('sortino_ratio', 0):.2f}"])
    writer.writerow(['Max Drawdown %', f"{result.get('max_drawdown_pct', 0):.2f}"])
    writer.writerow(['Win Rate %', f"{result.get('win_rate_pct', 0):.1f}"])
    writer.writerow([])
    
    # Yearly returns
    if 'yearly_returns' in result:
        writer.writerow(['=== Yearly Returns ==='])
        writer.writerow(['Year', 'Return %'])
        for yr in result['yearly_returns']:
            writer.writerow([yr['year'], f"{yr['return']:.2f}"])
        writer.writerow([])
    
    # Equity curve
    if 'equity_curve' in result:
        writer.writerow(['=== Equity Curve ==='])
        writer.writerow(['Date', 'Value'])
        for point in result['equity_curve']:
            writer.writerow([point.get('date', ''), f"{point.get('value', 0):.2f}"])
    
    return output.getvalue()


def export_portfolio_to_csv(holdings: List[Dict[str, Any]], portfolio_name: str) -> str:
    """Export portfolio holdings to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Portfolio', portfolio_name])
    writer.writerow(['Date', date.today().isoformat()])
    writer.writerow([])
    writer.writerow(['Ticker', 'Strategy', 'Weight %', 'Shares', 'Value'])
    
    for h in holdings:
        writer.writerow([
            h.get('ticker', ''),
            h.get('strategy', ''),
            f"{h.get('weight', 0) * 100:.1f}",
            h.get('shares', ''),
            f"{h.get('value', 0):.2f}" if h.get('value') else ''
        ])
    
    return output.getvalue()


def export_comparison_to_csv(comparison: Dict[str, Any]) -> str:
    """Export strategy comparison to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['=== Strategy Comparison ==='])
    writer.writerow(['Period', comparison.get('period', '')])
    writer.writerow([])
    writer.writerow(['Rank', 'Strategy', 'CAGR %', 'Sharpe', 'Max DD %', 'Win Rate %'])
    
    for i, s in enumerate(comparison.get('summary', []), 1):
        writer.writerow([
            i,
            s.get('strategy', ''),
            f"{s.get('cagr', 0):.1f}",
            f"{s.get('sharpe', 0):.2f}",
            f"{s.get('max_dd', 0):.1f}",
            f"{s.get('win_rate', 0):.0f}"
        ])
    
    return output.getvalue()
