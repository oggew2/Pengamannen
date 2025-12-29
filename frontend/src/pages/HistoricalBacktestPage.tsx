import { useState } from 'react';
import { BacktestChart } from '../components/BacktestChart';
import styles from '../styles/App.module.css';

interface YearlyReturn {
  year: number;
  return: number;
}

interface HistoricalResult {
  strategy_name: string;
  start_date: string;
  end_date: string;
  years: number;
  initial_capital: number;
  final_value: number;
  total_return_pct: number;
  cagr_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  best_year: YearlyReturn;
  worst_year: YearlyReturn;
  rebalance_count: number;
  yearly_returns: YearlyReturn[];
  equity_curve: { date: string; value: number }[];
  data_source: string;
}

interface CompareResult {
  period: string;
  summary: { strategy: string; cagr: number; sharpe: number; max_dd: number; win_rate: number }[];
}

const STRATEGIES = [
  { value: 'sammansatt_momentum', label: 'Sammansatt Momentum' },
  { value: 'trendande_varde', label: 'Trendande Värde' },
  { value: 'trendande_utdelning', label: 'Trendande Utdelning' },
  { value: 'trendande_kvalitet', label: 'Trendande Kvalitet' },
];

export function HistoricalBacktestPage() {
  const [strategy, setStrategy] = useState('sammansatt_momentum');
  const [startYear, setStartYear] = useState(2005);
  const [endYear, setEndYear] = useState(2024);
  const [result, setResult] = useState<HistoricalResult | null>(null);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runBacktest = async () => {
    setLoading(true);
    setError('');
    setCompareResult(null);
    try {
      const res = await fetch(`/api/backtesting/historical?strategy_name=${strategy}&start_year=${startYear}&end_year=${endYear}&use_synthetic=true`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Backtest failed');
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError('Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  const compareAll = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await fetch(`/api/backtesting/historical/compare?start_year=${startYear}&end_year=${endYear}`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Compare failed');
      const data = await res.json();
      setCompareResult(data);
    } catch (e) {
      setError('Failed to compare strategies');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className={styles.pageTitle}>Historical Backtest (20+ Years)</h1>

      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Configuration</h3>
          
          <label className={styles.formLabel}>Strategy</label>
          <select value={strategy} onChange={e => setStrategy(e.target.value)} className={styles.select}>
            {STRATEGIES.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>

          <label className={styles.formLabel}>Start Year</label>
          <input
            type="number"
            min={1990}
            max={2023}
            value={startYear}
            onChange={e => setStartYear(Number(e.target.value))}
            className={styles.input}
          />

          <label className={styles.formLabel}>End Year</label>
          <input
            type="number"
            min={2000}
            max={2024}
            value={endYear}
            onChange={e => setEndYear(Number(e.target.value))}
            className={styles.input}
          />

          <button onClick={runBacktest} disabled={loading} className={styles.btn}>
            {loading ? 'Running...' : 'Run Single Strategy'}
          </button>
          
          <button onClick={compareAll} disabled={loading} className={styles.btn} style={{marginTop: '0.5rem', background: '#3b82f6'}}>
            {loading ? 'Comparing...' : 'Compare All Strategies'}
          </button>

          {error && <p className={styles.error}>{error}</p>}
        </div>

        {result && (
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Results: {result.strategy_name}</h3>
            <p className={styles.cardMeta}>{result.years} years ({result.start_date} to {result.end_date})</p>
            <p className={styles.cardMeta}>Data: {result.data_source}</p>
            
            <div className={styles.statsGrid}>
              <div className={styles.stat}>
                <div className={styles.statValue} style={{color: result.cagr_pct >= 0 ? '#0d9488' : '#dc3545'}}>
                  {result.cagr_pct.toFixed(1)}%
                </div>
                <div className={styles.statLabel}>CAGR</div>
              </div>
              <div className={styles.stat}>
                <div className={styles.statValue}>{result.sharpe_ratio.toFixed(2)}</div>
                <div className={styles.statLabel}>Sharpe</div>
              </div>
              <div className={styles.stat}>
                <div className={styles.statValue} style={{color: '#dc3545'}}>
                  {result.max_drawdown_pct.toFixed(1)}%
                </div>
                <div className={styles.statLabel}>Max DD</div>
              </div>
            </div>

            <div style={{marginTop: '1rem', fontSize: '0.875rem'}}>
              <p>💰 Final Value: <strong>${result.final_value.toLocaleString()}</strong></p>
              <p>📈 Total Return: <strong>{result.total_return_pct.toFixed(1)}%</strong></p>
              <p>🎯 Win Rate: <strong>{result.win_rate_pct.toFixed(0)}%</strong> of years positive</p>
              <p>🏆 Best Year: <strong>{result.best_year.year}</strong> ({result.best_year.return.toFixed(1)}%)</p>
              <p>📉 Worst Year: <strong>{result.worst_year.year}</strong> ({result.worst_year.return.toFixed(1)}%)</p>
              <p>🔄 Rebalances: <strong>{result.rebalance_count}</strong></p>
            </div>
          </div>
        )}
      </div>

      {result?.equity_curve && (
        <div className={styles.card} style={{marginTop: '1.5rem'}}>
          <h3 className={styles.cardTitle}>Equity Curve</h3>
          <BacktestChart
            values={result.equity_curve.map(e => e.value)}
            labels={[result.start_date, result.end_date]}
          />
        </div>
      )}

      {result?.yearly_returns && (
        <div className={styles.card} style={{marginTop: '1.5rem'}}>
          <h3 className={styles.cardTitle}>Yearly Returns</h3>
          <div style={{display: 'flex', flexWrap: 'wrap', gap: '0.5rem'}}>
            {result.yearly_returns.map(yr => (
              <div
                key={yr.year}
                style={{
                  padding: '0.5rem',
                  borderRadius: '4px',
                  background: yr.return >= 0 ? '#d1fae5' : '#fee2e2',
                  color: yr.return >= 0 ? '#065f46' : '#991b1b',
                  fontSize: '0.75rem',
                  textAlign: 'center',
                  minWidth: '60px'
                }}
              >
                <div style={{fontWeight: 600}}>{yr.year}</div>
                <div>{yr.return.toFixed(1)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {compareResult && (
        <div className={styles.card} style={{marginTop: '1.5rem'}}>
          <h3 className={styles.cardTitle}>Strategy Comparison</h3>
          <p className={styles.cardMeta}>{compareResult.period}</p>
          
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Strategy</th>
                <th>CAGR</th>
                <th>Sharpe</th>
                <th>Max DD</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {compareResult.summary.map((s, i) => (
                <tr key={s.strategy}>
                  <td>{i + 1}</td>
                  <td>{s.strategy}</td>
                  <td style={{color: s.cagr >= 0 ? '#0d9488' : '#dc3545'}}>{s.cagr.toFixed(1)}%</td>
                  <td>{s.sharpe.toFixed(2)}</td>
                  <td style={{color: '#dc3545'}}>{s.max_dd.toFixed(1)}%</td>
                  <td>{s.win_rate.toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
