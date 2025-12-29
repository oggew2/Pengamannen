import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { StrategyTable } from '../components/StrategyTable';
import type { RankedStock } from '../types';
import styles from '../styles/App.module.css';

const STRATEGY_MAP: Record<string, {name: string, apiName: string, keyMetric: string}> = {
  momentum: { name: 'Sammansatt Momentum', apiName: 'sammansatt_momentum', keyMetric: 'Momentum' },
  value: { name: 'Trendande Värde', apiName: 'trendande_varde', keyMetric: 'P/E' },
  dividend: { name: 'Trendande Utdelning', apiName: 'trendande_utdelning', keyMetric: 'Yield' },
  quality: { name: 'Trendande Kvalitet', apiName: 'trendande_kvalitet', keyMetric: 'ROE' },
};

export function StrategyPage() {
  const { type } = useParams<{type: string}>();
  const [stocks, setStocks] = useState<RankedStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const config = type ? STRATEGY_MAP[type] : null;

  useEffect(() => {
    if (!config) {
      setError('Unknown strategy');
      setLoading(false);
      return;
    }
    api.getStrategyRankings(config.apiName)
      .then(setStocks)
      .catch(() => setError('Failed to load'))
      .finally(() => setLoading(false));
  }, [config]);

  if (loading) return <div className={styles.loading}>Loading...</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (!config) return <div className={styles.error}>Strategy not found</div>;

  return (
    <div>
      <h1 className={styles.pageTitle}>{config.name}</h1>
      <StrategyTable stocks={stocks} keyMetricLabel={config.keyMetric} />
    </div>
  );
}
