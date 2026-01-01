import { Link } from 'react-router-dom';
import type { RankedStock } from '../types';
import styles from '../styles/App.module.css';

interface Props {
  stocks: RankedStock[];
}

export function StrategyTable({ stocks }: Props) {
  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Ticker</th>
            <th>Company</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {stocks.map(s => (
            <tr key={s.ticker}>
              <td>{s.rank}</td>
              <td>
                <Link to={`/stock/${s.ticker}`} style={{ color: 'var(--color-primary)', textDecoration: 'none' }}>
                  {s.ticker}
                </Link>
              </td>
              <td>{s.name || '—'}</td>
              <td>{s.score.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
