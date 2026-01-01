import { useState, useEffect } from 'react';
import { formatSEK, formatPercent } from '../utils/format';
import styles from '../styles/App.module.css';

interface CostData {
  total_traded: number;
  courtage: number;
  spread_estimate: number;
  total_cost: number;
  cost_percentage: number;
}

export default function CostAnalysisPage() {
  const [portfolioValue, setPortfolioValue] = useState(100000);
  const [rebalancesPerYear, setRebalancesPerYear] = useState(4);
  const [turnover, setTurnover] = useState(50); // % of portfolio traded per rebalance
  const [costs, setCosts] = useState<CostData | null>(null);

  useEffect(() => {
    // Calculate costs
    const totalTraded = portfolioValue * (turnover / 100) * rebalancesPerYear;
    const courtageRate = 0.00069; // Avanza 0.069%
    const spreadRate = 0.002; // ~0.2% spread
    
    const courtage = totalTraded * courtageRate;
    const spread = totalTraded * spreadRate;
    const total = courtage + spread;
    
    setCosts({
      total_traded: totalTraded,
      courtage,
      spread_estimate: spread,
      total_cost: total,
      cost_percentage: (total / portfolioValue) * 100
    });
  }, [portfolioValue, rebalancesPerYear, turnover]);

  return (
    <div style={{ padding: '1rem' }}>
      <h1 className={styles.pageTitle}>Cost Analysis</h1>
      <p style={{ marginBottom: '1.5rem', color: '#666' }}>Estimate your annual trading costs</p>

      <div className={styles.card} style={{ marginBottom: '1.5rem' }}>
        <h3 className={styles.cardTitle}>Your Portfolio</h3>
        <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          <div>
            <label htmlFor="cost-value" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Portfolio Value (SEK)</label>
            <input id="cost-value" className={styles.input} type="number" value={portfolioValue} onChange={e => setPortfolioValue(+e.target.value)} />
          </div>
          <div>
            <label htmlFor="cost-rebalances" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Rebalances per Year</label>
            <select id="cost-rebalances" className={styles.select} value={rebalancesPerYear} onChange={e => setRebalancesPerYear(+e.target.value)}>
              <option value={1}>1 (Annual)</option>
              <option value={2}>2 (Semi-annual)</option>
              <option value={4}>4 (Quarterly)</option>
              <option value={12}>12 (Monthly)</option>
            </select>
          </div>
          <div>
            <label htmlFor="cost-turnover" style={{ display: 'block', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Turnover per Rebalance (%)</label>
            <input id="cost-turnover" className={styles.input} type="number" value={turnover} onChange={e => setTurnover(+e.target.value)} min={0} max={100} />
          </div>
        </div>
      </div>

      {costs && (
        <div className={styles.statsGrid} style={{ marginBottom: '1.5rem' }}>
          <div className={styles.stat}>
            <div className={styles.statValue}>{formatSEK(costs.total_cost)}</div>
            <div className={styles.statLabel}>Annual Cost</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statValue}>{formatPercent(costs.cost_percentage)}</div>
            <div className={styles.statLabel}>Cost Ratio</div>
          </div>
          <div className={styles.stat}>
            <div className={styles.statValue}>{formatSEK(costs.total_traded)}</div>
            <div className={styles.statLabel}>Total Traded</div>
          </div>
        </div>
      )}

      {costs && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>Cost Breakdown</h3>
          <table className={styles.table}>
            <tbody>
              <tr><td>Courtage (0.069%)</td><td style={{ textAlign: 'right' }}>{formatSEK(costs.courtage)}</td></tr>
              <tr><td>Spread estimate (0.2%)</td><td style={{ textAlign: 'right' }}>{formatSEK(costs.spread_estimate)}</td></tr>
              <tr style={{ fontWeight: 600 }}><td>Total</td><td style={{ textAlign: 'right' }}>{formatSEK(costs.total_cost)}</td></tr>
            </tbody>
          </table>
          
          <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#f0fdf4', borderRadius: '4px', fontSize: '0.875rem' }}>
            <strong>Tip:</strong> Börslabbet strategies typically have 30-50% turnover per rebalance. 
            Lower turnover = lower costs. Quarterly rebalancing (Momentum) costs more than annual (Värde/Utdelning/Kvalitet).
          </div>
        </div>
      )}

      <div className={styles.card} style={{ marginTop: '1.5rem' }}>
        <h3 className={styles.cardTitle}>Avanza Fee Structure</h3>
        <table className={styles.table}>
          <thead><tr><th>Fee Type</th><th>Rate</th><th>Notes</th></tr></thead>
          <tbody>
            <tr><td>Courtage (Mini)</td><td>0.25%</td><td>Min 1 kr</td></tr>
            <tr><td>Courtage (Standard)</td><td>0.069%</td><td>Min 1 kr, used in calculations</td></tr>
            <tr><td>Spread (Large Cap)</td><td>~0.1-0.2%</td><td>Varies by liquidity</td></tr>
            <tr><td>Spread (Small Cap)</td><td>~0.3-0.5%</td><td>Less liquid stocks</td></tr>
            <tr><td>ISK Tax</td><td>~0.4%/year</td><td>Based on government rate</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
