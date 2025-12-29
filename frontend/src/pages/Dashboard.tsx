import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { PortfolioSummary } from '../components/PortfolioSummary';
import { RebalanceCalendar } from '../components/RebalanceCalendar';
import type { StrategyMeta, RankedStock, PortfolioResponse, RebalanceDate } from '../types';
import styles from '../styles/App.module.css';

const STRATEGY_ROUTES: Record<string, string> = {
  sammansatt_momentum: '/strategies/momentum',
  trendande_varde: '/strategies/value',
  trendande_utdelning: '/strategies/dividend',
  trendande_kvalitet: '/strategies/quality',
};

const BACKTEST_DATA: Record<string, {return: number, sharpe: number, drawdown: number}> = {
  sammansatt_momentum: { return: 29.7, sharpe: 1.12, drawdown: -50 },
  trendande_varde: { return: 19.9, sharpe: 0.90, drawdown: -54 },
  trendande_utdelning: { return: 23.1, sharpe: 1.05, drawdown: -54 },
  trendande_kvalitet: { return: 22.7, sharpe: 0.96, drawdown: -58 },
};

export function Dashboard() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [top3, setTop3] = useState<Record<string, RankedStock[]>>({});
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [rebalanceDates, setRebalanceDates] = useState<RebalanceDate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getStrategies(),
      api.getPortfolio(),
      api.getRebalanceDates(),
    ]).then(async ([strats, port, dates]) => {
      setStrategies(strats);
      setPortfolio(port);
      setRebalanceDates(dates);
      
      const tops: Record<string, RankedStock[]> = {};
      for (const s of strats) {
        try {
          const rankings = await api.getStrategyTop10(s.name);
          tops[s.name] = rankings.slice(0, 3);
        } catch { /* empty */ }
      }
      setTop3(tops);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className={styles.loading}>Loading...</div>;

  return (
    <div>
      <h1 className={styles.pageTitle}>Dashboard</h1>
      
      <div className={styles.grid}>
        {strategies.map(s => (
          <div key={s.name} className={styles.card}>
            <h3 className={styles.cardTitle}>{s.display_name}</h3>
            <p className={styles.cardMeta}>{s.description}</p>
            
            {BACKTEST_DATA[s.name] && (
              <div style={{display: 'flex', gap: '1rem', marginBottom: '0.5rem'}}>
                <div className={styles.stat}>
                  <div className={styles.statValue}>{BACKTEST_DATA[s.name].return}%</div>
                  <div className={styles.statLabel}>Annual Return</div>
                </div>
                <div className={styles.stat}>
                  <div className={styles.statValue}>{BACKTEST_DATA[s.name].sharpe}</div>
                  <div className={styles.statLabel}>Sharpe</div>
                </div>
              </div>
            )}
            
            <ul className={styles.stockList}>
              {(top3[s.name] || []).map(stock => (
                <li key={stock.ticker}><span>{stock.ticker}</span> {stock.name || ''}</li>
              ))}
            </ul>
            <Link to={STRATEGY_ROUTES[s.name] || '/'} className={styles.cardLink}>View all →</Link>
          </div>
        ))}
      </div>

      <div className={styles.grid} style={{marginTop: '2rem'}}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Portfolio Composition</h3>
          {portfolio && <PortfolioSummary holdings={portfolio.holdings} />}
        </div>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Rebalance Calendar</h3>
          <RebalanceCalendar dates={rebalanceDates} />
        </div>
      </div>
    </div>
  );
}
