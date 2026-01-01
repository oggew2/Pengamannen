import { useState, useEffect } from 'react';
import { SectorPieChart } from '../components/SectorPieChart';
import { DrawdownChart } from '../components/DrawdownChart';
import { RollingSharpeChart } from '../components/RollingSharpeChart';
import { RiskMetricsCard } from '../components/RiskMetricsCard';
import { ExportButton } from '../components/ExportButton';
import { api } from '../api/client';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import styles from '../styles/App.module.css';

const STRATEGIES = ['momentum', 'value', 'dividend', 'quality'];
const BENCHMARKS = [
  { id: 'omxs30', name: 'OMXS30' },
  { id: 'sixrx', name: 'SIX Return' },
];

export default function AnalyticsDashboard() {
  const [strategy, setStrategy] = useState('momentum');
  const [period, setPeriod] = useState('1y');
  const [benchmark, setBenchmark] = useState('omxs30');
  const [sectorData, setSectorData] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [drawdown, setDrawdown] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [sec, perf, dd, comp] = await Promise.all([
          api.get(`/analytics/sector-allocation?strategy=${strategy}`),
          api.get(`/analytics/performance-metrics?strategy=${strategy}&period=${period}`),
          api.get(`/analytics/drawdown-periods?strategy=${strategy}`),
          api.get(`/benchmarks/compare?strategy=${strategy}&benchmark=${benchmark}&period=${period}`)
        ]);
        setSectorData(sec);
        setMetrics(perf);
        setDrawdown(dd);
        setComparison(comp);
      } catch (e) {
        console.error(e);
      }
      setLoading(false);
    }
    load();
  }, [strategy, period, benchmark]);

  return (
    <div style={{ padding: '1rem' }}>
      <h1>Analytics Dashboard</h1>
      
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <select value={strategy} onChange={e => setStrategy(e.target.value)} style={{ padding: '0.5rem' }}>
          {STRATEGIES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
        </select>
        <select value={period} onChange={e => setPeriod(e.target.value)} style={{ padding: '0.5rem' }}>
          <option value="1m">1 Month</option>
          <option value="3m">3 Months</option>
          <option value="6m">6 Months</option>
          <option value="1y">1 Year</option>
          <option value="3y">3 Years</option>
        </select>
        <select value={benchmark} onChange={e => setBenchmark(e.target.value)} style={{ padding: '0.5rem' }}>
          {BENCHMARKS.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
        <ExportButton url={`/export/analytics/${strategy}`} label="Export" />
      </div>

      {loading ? <p>Loading...</p> : (
        <div style={{ display: 'grid', gap: '2rem' }}>
          <section>
            <h2>Risk Metrics</h2>
            <RiskMetricsCard metrics={metrics} />
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>
            <section>
              <h2>Sector Allocation</h2>
              <SectorPieChart data={sectorData?.sectors || []} />
              {sectorData?.concentration && (
                <p style={{ color: '#888', fontSize: '0.9rem' }}>
                  Top sector: {sectorData.concentration.top_sector_pct}% · 
                  Top 3: {sectorData.concentration.top_3_sectors_pct}% · 
                  {sectorData.concentration.num_sectors} sectors
                </p>
              )}
            </section>

            <section>
              <h2>Rolling Sharpe Ratio</h2>
              <RollingSharpeChart data={metrics?.rolling_sharpe || []} />
            </section>
          </div>

          <section>
            <h2>Drawdown Analysis</h2>
            <DrawdownChart 
              data={drawdown?.chart_data || []} 
              maxDrawdown={drawdown?.max_drawdown_pct}
              currentDrawdown={drawdown?.current_drawdown_pct}
            />
            {drawdown?.worst_drawdowns?.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <h4>Worst Drawdown Periods</h4>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #ddd' }}>
                      <th style={{ textAlign: 'left', padding: '0.5rem' }}>Max DD</th>
                      <th style={{ textAlign: 'left', padding: '0.5rem' }}>Duration (days)</th>
                      <th style={{ textAlign: 'left', padding: '0.5rem' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drawdown.worst_drawdowns.slice(0, 5).map((d: any, i: number) => (
                      <tr key={i} style={{ borderBottom: '1px solid #eee' }}>
                        <td style={{ padding: '0.5rem', color: '#ef4444' }}>{d.max_dd}%</td>
                        <td style={{ padding: '0.5rem' }}>{d.length}</td>
                        <td style={{ padding: '0.5rem' }}>{d.ongoing ? '🔴 Ongoing' : '✅ Recovered'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {comparison?.chart_data && (
            <section className={styles.card} style={{ marginTop: '2rem' }}>
              <h2>Benchmark Comparison: {comparison.benchmark}</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div className={styles.stat}>
                  <div className={styles.statValue} style={{ color: (comparison.metrics?.excess_return_pct || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                    {comparison.metrics?.excess_return_pct > 0 ? '+' : ''}{comparison.metrics?.excess_return_pct}%
                  </div>
                  <div className={styles.statLabel}>Excess Return</div>
                </div>
                <div className={styles.stat}>
                  <div className={styles.statValue}>{comparison.metrics?.alpha_pct}%</div>
                  <div className={styles.statLabel}>Alpha</div>
                </div>
                <div className={styles.stat}>
                  <div className={styles.statValue}>{comparison.metrics?.beta}</div>
                  <div className={styles.statLabel}>Beta</div>
                </div>
                <div className={styles.stat}>
                  <div className={styles.statValue}>{comparison.metrics?.information_ratio}</div>
                  <div className={styles.statLabel}>Info Ratio</div>
                </div>
              </div>
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer>
                  <LineChart data={comparison.chart_data.dates.map((d: string, i: number) => ({
                    date: d,
                    strategy: comparison.chart_data.strategy[i],
                    benchmark: comparison.chart_data.benchmark[i]
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                    <YAxis domain={['auto', 'auto']} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="strategy" stroke="var(--color-primary)" dot={false} name="Strategy" />
                    <Line type="monotone" dataKey="benchmark" stroke="#888" dot={false} name={comparison.benchmark} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
