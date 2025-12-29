import { useState } from 'react';
import type { RankedStock, StockDetail } from '../types';
import { api } from '../api/client';
import styles from '../styles/App.module.css';

interface Props {
  stocks: RankedStock[];
  keyMetricLabel?: string;
}

export function StrategyTable({ stocks, keyMetricLabel = 'Score' }: Props) {
  const [selected, setSelected] = useState<StockDetail | null>(null);

  const handleClick = async (ticker: string) => {
    try {
      const detail = await api.getStock(ticker);
      setSelected(detail);
    } catch {
      // Stock not found in DB
    }
  };

  return (
    <>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Ticker</th>
            <th>Company</th>
            <th>Score</th>
            {keyMetricLabel !== 'Score' && <th>{keyMetricLabel}</th>}
          </tr>
        </thead>
        <tbody>
          {stocks.map(s => (
            <tr key={s.ticker} className={styles.tableClickable} onClick={() => handleClick(s.ticker)}>
              <td>{s.rank}</td>
              <td>{s.ticker}</td>
              <td>{s.name || '—'}</td>
              <td>{s.score.toFixed(2)}</td>
              {keyMetricLabel !== 'Score' && <td>—</td>}
            </tr>
          ))}
        </tbody>
      </table>

      {selected && (
        <div className={styles.modal} onClick={() => setSelected(null)}>
          <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
            <button className={styles.modalClose} onClick={() => setSelected(null)}>×</button>
            <h2>{selected.ticker}</h2>
            <p>{selected.name || 'Unknown'}</p>
            <table className={styles.table} style={{marginTop: '1rem'}}>
              <tbody>
                {selected.pe && <tr><td>P/E</td><td>{selected.pe.toFixed(2)}</td></tr>}
                {selected.pb && <tr><td>P/B</td><td>{selected.pb.toFixed(2)}</td></tr>}
                {selected.dividend_yield && <tr><td>Dividend Yield</td><td>{(selected.dividend_yield * 100).toFixed(2)}%</td></tr>}
                {selected.roe && <tr><td>ROE</td><td>{(selected.roe * 100).toFixed(2)}%</td></tr>}
                {selected.return_12m && <tr><td>12M Return</td><td>{(selected.return_12m * 100).toFixed(2)}%</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
