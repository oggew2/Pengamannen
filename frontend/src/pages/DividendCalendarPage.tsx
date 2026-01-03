import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { queryKeys } from '../api/hooks';
import styles from '../styles/App.module.css';

interface DividendEvent {
  ticker: string;
  ex_date: string;
  payment_date: string;
  amount: number;
  currency: string;
}

interface Holding {
  ticker: string;
  shares: number;
}

export default function DividendCalendarPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem('myHoldings');
    if (saved) setHoldings(JSON.parse(saved));
  }, []);

  const { data: dividends = [], isLoading, isError } = useQuery({
    queryKey: queryKeys.dividends.upcoming(90),
    queryFn: () => api.get<DividendEvent[]>('/dividends/upcoming?days_ahead=90'),
  });

  const holdingTickers = new Set(holdings.map(h => h.ticker));
  const myDividends = dividends.filter(d => holdingTickers.has(d.ticker));
  const otherDividends = dividends.filter(d => !holdingTickers.has(d.ticker));
  const getShares = (ticker: string) => holdings.find(h => h.ticker === ticker)?.shares || 0;

  if (isError) return <div style={{ padding: '2rem', textAlign: 'center', color: '#ef4444' }}>Failed to load dividends</div>;
  if (isLoading) return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading...</div>;

  return (
    <div style={{ padding: '1rem' }}>
      <h1 className={styles.pageTitle}>Dividend Calendar</h1>
      <p style={{ marginBottom: '1.5rem', color: '#666' }}>Upcoming ex-dividend dates (next 90 days)</p>

      {myDividends.length > 0 && (
        <div className={styles.card} style={{ marginBottom: '1.5rem' }}>
          <h3 className={styles.cardTitle}>My Holdings</h3>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead><tr><th>Ticker</th><th>Ex-Date</th><th>Payment</th><th>Amount</th><th>Shares</th><th>Expected</th></tr></thead>
              <tbody>
                {myDividends.map((d, i) => {
                  const shares = getShares(d.ticker);
                  return (
                    <tr key={i}>
                      <td>{d.ticker.replace('.ST', '')}</td>
                      <td>{d.ex_date}</td>
                      <td>{d.payment_date || '—'}</td>
                      <td>{d.amount?.toFixed(2)} {d.currency}</td>
                      <td>{shares}</td>
                      <td style={{ fontWeight: 600 }}>{(d.amount * shares).toFixed(0)} {d.currency}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: '1rem', fontWeight: 600 }}>
            Total expected: {myDividends.reduce((sum, d) => sum + d.amount * getShares(d.ticker), 0).toFixed(0)} SEK
          </div>
        </div>
      )}

      {holdings.length === 0 && (
        <div className={styles.card} style={{ marginBottom: '1.5rem', textAlign: 'center', padding: '2rem' }}>
          <p>Add holdings in <a href="/rebalancing" style={{ color: '#3b82f6' }}>Min Strategi</a> to see your dividend calendar</p>
        </div>
      )}

      {otherDividends.length > 0 && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>All Upcoming Dividends</h3>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead><tr><th>Ticker</th><th>Ex-Date</th><th>Payment</th><th>Amount</th></tr></thead>
              <tbody>
                {otherDividends.slice(0, 20).map((d, i) => (
                  <tr key={i}>
                    <td>{d.ticker.replace('.ST', '')}</td>
                    <td>{d.ex_date}</td>
                    <td>{d.payment_date || '—'}</td>
                    <td>{d.amount?.toFixed(2)} {d.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {dividends.length === 0 && (
        <div className={styles.card} style={{ textAlign: 'center', padding: '2rem' }}>
          <p>No upcoming dividend events found</p>
        </div>
      )}
    </div>
  );
}
