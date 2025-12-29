import styles from '../styles/App.module.css';

interface Props {
  values: number[];
  labels?: string[];
}

export function BacktestChart({ values, labels }: Props) {
  if (!values.length) return null;
  
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  
  const width = 600;
  const height = 200;
  const padding = 40;
  
  const points = values.map((v, i) => {
    const x = padding + (i / (values.length - 1)) * (width - 2 * padding);
    const y = height - padding - ((v - min) / range) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(' ');
  
  return (
    <div className={styles.chartContainer}>
      <svg viewBox={`0 0 ${width} ${height}`} className={styles.chart}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(pct => {
          const y = height - padding - pct * (height - 2 * padding);
          const val = min + pct * range;
          return (
            <g key={pct}>
              <line x1={padding} y1={y} x2={width - padding} y2={y} stroke="#e9ecef" />
              <text x={padding - 5} y={y + 4} textAnchor="end" fontSize="10" fill="#6c757d">
                {val.toFixed(0)}
              </text>
            </g>
          );
        })}
        
        {/* Line */}
        <polyline
          points={points}
          fill="none"
          stroke="#0d9488"
          strokeWidth="2"
        />
        
        {/* Area */}
        <polygon
          points={`${padding},${height - padding} ${points} ${width - padding},${height - padding}`}
          fill="#0d9488"
          fillOpacity="0.1"
        />
      </svg>
      {labels && (
        <div className={styles.chartLabels}>
          <span>{labels[0]}</span>
          <span>{labels[labels.length - 1]}</span>
        </div>
      )}
    </div>
  );
}
