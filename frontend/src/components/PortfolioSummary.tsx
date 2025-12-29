import type { PortfolioHolding } from '../types';
import styles from '../styles/App.module.css';

const COLORS = ['#0d9488', '#3b82f6', '#f59e0b', '#ef4444'];

interface Props {
  holdings: PortfolioHolding[];
}

export function PortfolioSummary({ holdings }: Props) {
  const byStrategy = holdings.reduce((acc, h) => {
    acc[h.strategy] = (acc[h.strategy] || 0) + h.weight;
    return acc;
  }, {} as Record<string, number>);

  const strategies = Object.entries(byStrategy);
  let cumulative = 0;

  return (
    <div>
      <svg viewBox="0 0 100 100" className={styles.pieChart}>
        {strategies.map(([name, weight], i) => {
          const start = cumulative * 360;
          const angle = weight * 360;
          cumulative += weight;
          const large = angle > 180 ? 1 : 0;
          const startRad = (start - 90) * Math.PI / 180;
          const endRad = (start + angle - 90) * Math.PI / 180;
          const x1 = 50 + 40 * Math.cos(startRad);
          const y1 = 50 + 40 * Math.sin(startRad);
          const x2 = 50 + 40 * Math.cos(endRad);
          const y2 = 50 + 40 * Math.sin(endRad);
          return (
            <path
              key={name}
              d={`M 50 50 L ${x1} ${y1} A 40 40 0 ${large} 1 ${x2} ${y2} Z`}
              fill={COLORS[i % COLORS.length]}
            />
          );
        })}
      </svg>
      <div className={styles.legend}>
        {strategies.map(([name, weight], i) => (
          <div key={name} className={styles.legendItem}>
            <span className={styles.legendDot} style={{background: COLORS[i % COLORS.length]}} />
            {name}: {(weight * 100).toFixed(0)}%
          </div>
        ))}
      </div>
    </div>
  );
}
