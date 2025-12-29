import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { PortfolioSummary } from '../components/PortfolioSummary';
import { RebalanceCalendar } from '../components/RebalanceCalendar';
import type { PortfolioResponse, RebalanceDate } from '../types';
import styles from '../styles/App.module.css';

export function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [rebalanceDates, setRebalanceDates] = useState<RebalanceDate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getPortfolio(), api.getRebalanceDates()])
      .then(([p, d]) => { setPortfolio(p); setRebalanceDates(d); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className={styles.loading}>Loading...</div>;
  if (!portfolio) return <div className={styles.error}>Failed to load portfolio</div>;

  return (
    <div>
      <h1 className={styles.pageTitle}>Svenska Portföljen</h1>
      
      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Composition</h3>
          <PortfolioSummary holdings={portfolio.holdings} />
        </div>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Next Rebalance</h3>
          <div className={styles.stat}>
            <div className={styles.statValue}>{portfolio.next_rebalance_date || '—'}</div>
            <div className={styles.statLabel}>As of {portfolio.as_of_date}</div>
          </div>
        </div>
      </div>

      <div className={styles.card} style={{marginTop: '1.5rem'}}>
        <h3 className={styles.cardTitle}>Holdings</h3>
        <table className={styles.table}>
          <thead>
            <tr><th>Ticker</th><th>Name</th><th>Strategy</th><th>Weight</th></tr>
          </thead>
          <tbody>
            {portfolio.holdings.map((h, i) => (
              <tr key={`${h.ticker}-${h.strategy}-${i}`}>
                <td>{h.ticker}</td>
                <td>{h.name || '—'}</td>
                <td>{h.strategy}</td>
                <td>{(h.weight * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.card} style={{marginTop: '1.5rem'}}>
        <h3 className={styles.cardTitle}>Rebalance Calendar</h3>
        <RebalanceCalendar dates={rebalanceDates} />
      </div>
    </div>
  );
}
