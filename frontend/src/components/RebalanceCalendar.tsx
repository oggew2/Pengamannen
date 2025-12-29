import type { RebalanceDate } from '../types';
import styles from '../styles/App.module.css';

const STRATEGY_NAMES: Record<string, string> = {
  sammansatt_momentum: 'Sammansatt Momentum',
  trendande_varde: 'Trendande Värde',
  trendande_utdelning: 'Trendande Utdelning',
  trendande_kvalitet: 'Trendande Kvalitet',
};

interface Props {
  dates: RebalanceDate[];
}

export function RebalanceCalendar({ dates }: Props) {
  const sorted = [...dates].sort((a, b) => a.next_date.localeCompare(b.next_date));

  return (
    <div className={styles.calendar}>
      {sorted.map(d => (
        <div key={d.strategy_name} className={styles.calendarItem}>
          <span>{STRATEGY_NAMES[d.strategy_name] || d.strategy_name}</span>
          <span className={styles.calendarDate}>{d.next_date}</span>
        </div>
      ))}
    </div>
  );
}
