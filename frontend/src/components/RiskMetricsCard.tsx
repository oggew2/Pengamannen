interface Props {
  metrics: {
    total_return_pct?: number;
    annualized_return_pct?: number;
    annualized_volatility_pct?: number;
    sharpe_ratio?: number;
    sortino_ratio?: number;
    max_drawdown_pct?: number;
    positive_days_pct?: number;
    best_day_pct?: number;
    worst_day_pct?: number;
  };
}

export function RiskMetricsCard({ metrics }: Props) {
  if (!metrics) return null;

  const items = [
    { label: 'Total Return', value: `${metrics.total_return_pct?.toFixed(1)}%`, good: (metrics.total_return_pct || 0) > 0 },
    { label: 'Ann. Return', value: `${metrics.annualized_return_pct?.toFixed(1)}%`, good: (metrics.annualized_return_pct || 0) > 0 },
    { label: 'Volatility', value: `${metrics.annualized_volatility_pct?.toFixed(1)}%`, good: (metrics.annualized_volatility_pct || 0) < 20 },
    { label: 'Sharpe', value: metrics.sharpe_ratio?.toFixed(2), good: (metrics.sharpe_ratio || 0) > 1 },
    { label: 'Sortino', value: metrics.sortino_ratio?.toFixed(2), good: (metrics.sortino_ratio || 0) > 1 },
    { label: 'Max DD', value: `${metrics.max_drawdown_pct?.toFixed(1)}%`, good: (metrics.max_drawdown_pct || 0) > -20 },
    { label: 'Win Rate', value: `${metrics.positive_days_pct?.toFixed(0)}%`, good: (metrics.positive_days_pct || 0) > 50 },
    { label: 'Best Day', value: `${metrics.best_day_pct?.toFixed(1)}%` },
    { label: 'Worst Day', value: `${metrics.worst_day_pct?.toFixed(1)}%` },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
      {items.map(({ label, value, good }) => (
        <div key={label} style={{ padding: '0.75rem', background: 'var(--card-bg, #f5f5f5)', borderRadius: '8px' }}>
          <div style={{ fontSize: '0.8rem', color: '#888' }}>{label}</div>
          <div style={{ fontSize: '1.2rem', fontWeight: 600, color: good === undefined ? 'inherit' : good ? '#22c55e' : '#ef4444' }}>
            {value || '-'}
          </div>
        </div>
      ))}
    </div>
  );
}
