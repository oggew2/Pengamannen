import { useState } from 'react';
import { api } from '../api/client';
import { formatSEK, formatSEKWithSign } from '../utils/format';
import styles from '../styles/App.module.css';

interface GoalResult {
  name: string;
  target_amount: number;
  current_amount: number;
  progress_pct: number;
  months_remaining: number;
  required_annual_return_pct: number;
  on_track: boolean;
  recommendation: string;
}

interface Projection {
  year: number;
  value: number;
  contributions: number;
}

export default function GoalsPage() {
  const [goal, setGoal] = useState<GoalResult | null>(null);
  const [projections, setProjections] = useState<Projection[]>([]);
  
  const [name, setName] = useState('Pension');
  const [target, setTarget] = useState(5000000);
  const [current, setCurrent] = useState(500000);
  const [monthly, setMonthly] = useState(10000);
  const [targetDate, setTargetDate] = useState('2045-01-01');
  const [expectedReturn, setExpectedReturn] = useState(8);

  const calculate = async () => {
    const g = await api.post<GoalResult>(`/goals?name=${name}&target_amount=${target}&current_amount=${current}&monthly_contribution=${monthly}&target_date=${targetDate}`, {});
    setGoal(g);
    
    const years = Math.ceil(g.months_remaining / 12);
    const p = await api.get<{ projections: Projection[] }>(`/goals/projection?current_amount=${current}&monthly_contribution=${monthly}&years=${years}&expected_return=${expectedReturn}`);
    setProjections(p.projections);
  };

  return (
    <div style={{ padding: '1rem' }}>
      <h1 className={styles.pageTitle}>Financial Goals</h1>
      
      <div className={styles.grid}>
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Set Your Goal</h3>
          
          <label htmlFor="goal-name" className={styles.formLabel}>Goal Name</label>
          <input id="goal-name" className={styles.input} value={name} onChange={e => setName(e.target.value)} />
          
          <label htmlFor="goal-target" className={styles.formLabel}>Target Amount (SEK)</label>
          <input id="goal-target" className={styles.input} type="number" value={target} onChange={e => setTarget(+e.target.value)} />
          
          <label htmlFor="goal-current" className={styles.formLabel}>Current Savings (SEK)</label>
          <input id="goal-current" className={styles.input} type="number" value={current} onChange={e => setCurrent(+e.target.value)} />
          
          <label htmlFor="goal-monthly" className={styles.formLabel}>Monthly Contribution (SEK)</label>
          <input id="goal-monthly" className={styles.input} type="number" value={monthly} onChange={e => setMonthly(+e.target.value)} />
          
          <label htmlFor="goal-date" className={styles.formLabel}>Target Date</label>
          <input id="goal-date" className={styles.input} type="date" value={targetDate} onChange={e => setTargetDate(e.target.value)} />
          
          <label htmlFor="goal-return" className={styles.formLabel}>Expected Annual Return (%)</label>
          <input id="goal-return" className={styles.input} type="number" value={expectedReturn} onChange={e => setExpectedReturn(+e.target.value)} />
          
          <button className={styles.btn} onClick={calculate}>Calculate</button>
        </div>
        
        {goal && (
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>{goal.name}</h3>
            
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ background: 'var(--color-border)', borderRadius: '4px', height: '20px', overflow: 'hidden' }}>
                <div style={{ 
                  width: `${Math.min(100, goal.progress_pct)}%`, 
                  height: '100%', 
                  background: goal.on_track ? 'var(--color-primary)' : '#ef4444',
                  transition: 'width 0.3s'
                }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                <span>{formatSEK(goal.current_amount)}</span>
                <span>{formatSEK(goal.target_amount)}</span>
              </div>
            </div>
            
            <div className={styles.statsGrid}>
              <div className={styles.stat}>
                <div className={styles.statValue}>{goal.progress_pct}%</div>
                <div className={styles.statLabel}>Progress</div>
              </div>
              <div className={styles.stat}>
                <div className={styles.statValue}>{goal.months_remaining}</div>
                <div className={styles.statLabel}>Months Left</div>
              </div>
              <div className={styles.stat}>
                <div className={styles.statValue} style={{ color: goal.on_track ? '#22c55e' : '#ef4444' }}>
                  {goal.required_annual_return_pct}%
                </div>
                <div className={styles.statLabel}>Required Return</div>
              </div>
            </div>
            
            <p style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--color-bg)', borderRadius: '6px', fontSize: '0.875rem' }}>
              💡 {goal.recommendation}
            </p>
          </div>
        )}
      </div>
      
      {projections.length > 0 && (
        <div className={styles.card} style={{ marginTop: '1.5rem' }}>
          <h3 className={styles.cardTitle}>Growth Projection</h3>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr><th>Year</th><th>Projected Value</th><th>Total Contributed</th><th>Growth</th></tr>
              </thead>
              <tbody>
                {projections.map(p => (
                  <tr key={p.year}>
                    <td>{p.year}</td>
                    <td>{formatSEK(p.value)}</td>
                    <td>{formatSEK(p.contributions)}</td>
                    <td style={{ color: '#22c55e' }}>{formatSEKWithSign(p.value - p.contributions)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
