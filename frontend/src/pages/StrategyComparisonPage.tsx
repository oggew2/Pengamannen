import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Link } from 'react-router-dom';
import styles from '../styles/App.module.css';

interface RankedStock {
  ticker: string;
  name: string;
  rank: number;
  score: number;
}

interface Strategy {
  name: string;
  display_name: string;
}

export default function StrategyComparisonPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [rankings, setRankings] = useState<Record<string, RankedStock[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<Strategy[]>('/strategies').then(async (strats) => {
      setStrategies(strats);
      const results: Record<string, RankedStock[]> = {};
      await Promise.all(strats.map(async (s) => {
        try {
          const data = await api.get<RankedStock[]>(`/strategies/${s.name}`);
          results[s.name] = data.slice(0, 10);
        } catch { results[s.name] = []; }
      }));
      setRankings(results);
      setLoading(false);
    });
  }, []);

  if (loading) return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading strategies...</div>;

  return (
    <div style={{ padding: '1rem' }}>
      <h1 className={styles.pageTitle}>Strategy Comparison</h1>
      <p style={{ marginBottom: '1.5rem', color: '#666' }}>Top 10 stocks from each Börslabbet strategy</p>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        {strategies.map(s => (
          <div key={s.name} className={styles.card}>
            <h3 className={styles.cardTitle}>{s.display_name}</h3>
            <table className={styles.table} style={{ fontSize: '0.9rem' }}>
              <thead><tr><th>#</th><th>Ticker</th><th>Score</th></tr></thead>
              <tbody>
                {rankings[s.name]?.map(stock => (
                  <tr key={stock.ticker}>
                    <td>{stock.rank}</td>
                    <td><Link to={`/stock/${stock.ticker}`} style={{ color: '#3b82f6' }}>{stock.ticker.replace('.ST', '')}</Link></td>
                    <td>{stock.score.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
