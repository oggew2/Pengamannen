import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { BacktestChart } from '../components/BacktestChart';
import type { StrategyMeta, BacktestResult } from '../types';
import styles from '../styles/App.module.css';

export function BacktestingPage() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [startDate, setStartDate] = useState('2020-01-01');
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [history, setHistory] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Customization options
  const [topN, setTopN] = useState(10);
  const [minMarketCap, setMinMarketCap] = useState(2000); // MSEK
  const [rebalanceFreq, setRebalanceFreq] = useState('quarterly');

  useEffect(() => {
    api.getStrategies().then(setStrategies).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedStrategy) {
      api.getBacktestResults(selectedStrategy).then(setHistory).catch(() => setHistory([]));
    }
  }, [selectedStrategy]);

  const handleRun = async () => {
    if (!selectedStrategy) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.runBacktest({
        strategy_name: selectedStrategy,
        start_date: startDate,
        end_date: endDate,
      });
      setResult(res);
      // Refresh history
      const h = await api.getBacktestResults(selectedStrategy);
      setHistory(h);
    } catch {
      setError('Failed to run backtest. Make sure you have price data loaded.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className={styles.pageTitle}>Backtesting</h1>

      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Run Backtest</h3>
          
          <label className={styles.formLabel}>Strategy</label>
          <select
            value={selectedStrategy}
            onChange={e => setSelectedStrategy(e.target.value)}
            className={styles.select}
          >
            <option value="">Select strategy...</option>
            {strategies.map(s => (
              <option key={s.name} value={s.name}>{s.display_name}</option>
            ))}
          </select>

          <label className={styles.formLabel}>Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            className={styles.input}
          />

          <label className={styles.formLabel}>End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={e => setEndDate(e.target.value)}
            className={styles.input}
          />

          <details style={{ marginTop: '1rem' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 500 }}>Advanced Options</summary>
            <div style={{ marginTop: '0.5rem' }}>
              <label className={styles.formLabel}>Top N Stocks</label>
              <select value={topN} onChange={e => setTopN(+e.target.value)} className={styles.select}>
                <option value={5}>5</option>
                <option value={10}>10 (Standard)</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
              </select>

              <label className={styles.formLabel}>Min Market Cap (MSEK)</label>
              <select value={minMarketCap} onChange={e => setMinMarketCap(+e.target.value)} className={styles.select}>
                <option value={500}>500 MSEK</option>
                <option value={1000}>1 000 MSEK</option>
                <option value={2000}>2 000 MSEK (Standard)</option>
                <option value={5000}>5 000 MSEK</option>
                <option value={10000}>10 000 MSEK</option>
              </select>

              <label className={styles.formLabel}>Rebalance Frequency</label>
              <select value={rebalanceFreq} onChange={e => setRebalanceFreq(e.target.value)} className={styles.select}>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly (Standard)</option>
                <option value="semi-annual">Semi-Annual</option>
                <option value="annual">Annual</option>
              </select>
            </div>
          </details>

          <button
            onClick={handleRun}
            disabled={loading || !selectedStrategy}
            className={styles.btn}
          >
            {loading ? 'Running...' : 'Run Backtest'}
          </button>

          {error && <p className={styles.error}>{error}</p>}
        </div>

        {result && (
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Results</h3>
            <div className={styles.statsGrid}>
              <div className={styles.stat}>
                <div className={styles.statValue} style={{ color: result.total_return_pct >= 0 ? '#0d9488' : '#dc3545' }}>
                  {result.total_return_pct.toFixed(1)}%
                </div>
                <div className={styles.statLabel}>Total Return</div>
              </div>
              <div className={styles.stat}>
                <div className={styles.statValue}>{result.sharpe.toFixed(2)}</div>
                <div className={styles.statLabel}>Sharpe Ratio</div>
              </div>
              <div className={styles.stat}>
                <div className={styles.statValue} style={{ color: '#dc3545' }}>
                  {result.max_drawdown_pct.toFixed(1)}%
                </div>
                <div className={styles.statLabel}>Max Drawdown</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {result?.portfolio_values && result.portfolio_values.length > 0 && (
        <div className={styles.card} style={{ marginTop: '1.5rem' }}>
          <h3 className={styles.cardTitle}>Equity Curve</h3>
          <BacktestChart
            values={result.portfolio_values}
            labels={[result.start_date, result.end_date]}
          />
        </div>
      )}

      {history.length > 0 && (
        <div className={styles.card} style={{ marginTop: '1.5rem' }}>
          <h3 className={styles.cardTitle}>Previous Backtests</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Period</th>
                <th>Return</th>
                <th>Sharpe</th>
                <th>Drawdown</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h, i) => (
                <tr key={i}>
                  <td>{h.strategy_name}</td>
                  <td>{h.start_date} → {h.end_date}</td>
                  <td style={{ color: h.total_return_pct >= 0 ? '#0d9488' : '#dc3545' }}>
                    {h.total_return_pct.toFixed(1)}%
                  </td>
                  <td>{h.sharpe.toFixed(2)}</td>
                  <td style={{ color: '#dc3545' }}>{h.max_drawdown_pct.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
