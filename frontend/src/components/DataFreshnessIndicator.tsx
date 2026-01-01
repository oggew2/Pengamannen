import { useState, useEffect } from 'react';
import { api } from '../api/client';
import styles from '../styles/App.module.css';

interface DataStatus {
  summary?: {
    total_stocks: number;
    fresh_count: number;
    stale_count: number;
    very_stale_count: number;
    fresh_percentage: number;
  };
  last_sync?: string;
}

export default function DataFreshnessIndicator() {
  const [status, setStatus] = useState<DataStatus | null>(null);

  useEffect(() => {
    api.get<DataStatus>('/data/status/detailed')
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status?.summary) return null;

  const { fresh_percentage, total_stocks } = status.summary;
  const color = fresh_percentage >= 80 ? '#22c55e' : fresh_percentage >= 50 ? '#f59e0b' : '#ef4444';
  const label = fresh_percentage >= 80 ? 'Fresh' : fresh_percentage >= 50 ? 'Stale' : 'Outdated';

  return (
    <div className={styles.freshnessIndicator} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#666' }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: color }} />
      <span>Data: {label} ({total_stocks} stocks, {fresh_percentage.toFixed(0)}% fresh)</span>
    </div>
  );
}
