import styles from '../styles/App.module.css';

interface Props {
  label: string;
  value: number;
  onChange: (value: number) => void;
  max?: number;
}

export function StrategyWeightSelector({ label, value, onChange, max = 100 }: Props) {
  return (
    <div className={styles.weightSelector}>
      <label className={styles.weightLabel}>
        <span>{label}</span>
        <span className={styles.weightValue}>{value}%</span>
      </label>
      <input
        type="range"
        min={0}
        max={max}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className={styles.weightSlider}
      />
    </div>
  );
}
