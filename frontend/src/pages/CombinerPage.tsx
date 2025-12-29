import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { StrategyWeightSelector } from '../components/StrategyWeightSelector';
import type { PortfolioResponse, SavedCombination } from '../types';
import styles from '../styles/App.module.css';

const STRATEGIES = [
  { key: 'sammansatt_momentum', label: 'Sammansatt Momentum' },
  { key: 'trendande_varde', label: 'Trendande Värde' },
  { key: 'trendande_utdelning', label: 'Trendande Utdelning' },
  { key: 'trendande_kvalitet', label: 'Trendande Kvalitet' },
];

const STORAGE_KEY = 'borslabbet_combinations';

export function CombinerPage() {
  const [weights, setWeights] = useState<Record<string, number>>({
    sammansatt_momentum: 25,
    trendande_varde: 25,
    trendande_utdelning: 25,
    trendande_kvalitet: 25,
  });
  const [name, setName] = useState('');
  const [result, setResult] = useState<PortfolioResponse | null>(null);
  const [saved, setSaved] = useState<SavedCombination[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setSaved(JSON.parse(stored));
  }, []);

  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  const handleWeightChange = (key: string, value: number) => {
    setWeights(prev => ({ ...prev, [key]: value }));
  };

  const handleCombine = async () => {
    if (total !== 100) {
      setError('Weights must sum to 100%');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const strategies = Object.entries(weights)
        .filter(([, w]) => w > 0)
        .map(([k]) => k);
      const res = await api.combinePortfolio({ strategies });
      setResult(res);
    } catch {
      setError('Failed to combine portfolio');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = () => {
    if (!name.trim()) return;
    const combo: SavedCombination = {
      name: name.trim(),
      weights: { ...weights },
      createdAt: new Date().toISOString(),
    };
    const updated = [...saved, combo];
    setSaved(updated);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    setName('');
  };

  const handleLoad = (combo: SavedCombination) => {
    setWeights(combo.weights);
  };

  const handleDelete = (index: number) => {
    const updated = saved.filter((_, i) => i !== index);
    setSaved(updated);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  };

  // Overlap analysis
  const overlapCount = result?.holdings.reduce((acc, h) => {
    acc[h.ticker] = (acc[h.ticker] || 0) + 1;
    return acc;
  }, {} as Record<string, number>) || {};
  const overlaps = Object.entries(overlapCount).filter(([, c]) => c > 1);

  return (
    <div>
      <h1 className={styles.pageTitle}>Portfolio Kombinator</h1>

      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Strategy Weights</h3>
          {STRATEGIES.map(s => (
            <StrategyWeightSelector
              key={s.key}
              label={s.label}
              value={weights[s.key]}
              onChange={v => handleWeightChange(s.key, v)}
            />
          ))}
          <div className={styles.weightTotal} style={{ color: total === 100 ? '#0d9488' : '#dc3545' }}>
            Total: {total}%
          </div>
          <button onClick={handleCombine} disabled={loading || total !== 100} className={styles.btn}>
            {loading ? 'Combining...' : 'Combine Portfolio'}
          </button>
          {error && <p className={styles.error}>{error}</p>}
        </div>

        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Save Combination</h3>
          <input
            type="text"
            placeholder="Combination name"
            value={name}
            onChange={e => setName(e.target.value)}
            className={styles.input}
          />
          <button onClick={handleSave} disabled={!name.trim()} className={styles.btn}>
            Save
          </button>

          {saved.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h4>Saved Combinations</h4>
              {saved.map((c, i) => (
                <div key={i} className={styles.savedItem}>
                  <span>{c.name}</span>
                  <div>
                    <button onClick={() => handleLoad(c)} className={styles.btnSmall}>Load</button>
                    <button onClick={() => handleDelete(i)} className={styles.btnSmall}>×</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {result && (
        <div className={styles.card} style={{ marginTop: '1.5rem' }}>
          <h3 className={styles.cardTitle}>Combined Holdings</h3>
          
          {overlaps.length > 0 && (
            <div className={styles.overlapBox}>
              <strong>Overlap:</strong> {overlaps.map(([t, c]) => `${t} (${c}x)`).join(', ')}
            </div>
          )}

          <table className={styles.table}>
            <thead>
              <tr><th>Ticker</th><th>Name</th><th>Strategy</th><th>Weight</th></tr>
            </thead>
            <tbody>
              {result.holdings.map((h, i) => (
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
      )}
    </div>
  );
}
