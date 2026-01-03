import { useState, useMemo } from 'react';
import { NativeSelect } from '@chakra-ui/react';
import styles from '../styles/App.module.css';

interface CostBreakdown {
  courtage: number;
  spread: number;
  totalPerRebalance: number;
  annualRebalanceCost: number;
  totalAnnualCost: number;
  costPct: number;
  netExpectedReturn: number;
  isViable: boolean;
  breakevenCapital: number;
}

const BROKERS = {
  avanza: { name: 'Avanza', minFee: 1, pct: 0.0015 },
  nordnet: { name: 'Nordnet', minFee: 39, pct: 0.0015 },
  degiro: { name: 'DEGIRO', minFee: 0, pct: 0.0005 },
};

const STRATEGIES = {
  sammansatt_momentum: { name: 'Sammansatt Momentum', rebalancesPerYear: 4, expectedReturn: 17.5, turnover: 0.6 },
  trendande_varde: { name: 'Trendande Värde', rebalancesPerYear: 1, expectedReturn: 15, turnover: 0.4 },
  trendande_utdelning: { name: 'Trendande Utdelning', rebalancesPerYear: 1, expectedReturn: 12.5, turnover: 0.3 },
  trendande_kvalitet: { name: 'Trendande Kvalitet', rebalancesPerYear: 1, expectedReturn: 14, turnover: 0.35 },
};

const ETF_ALTERNATIVES = [
  { name: 'Avanza Zero', ter: 0, description: 'Gratis indexfond (Sverige)' },
  { name: 'XACT OMXS30', ter: 0.1, description: 'ETF som följer OMXS30' },
  { name: 'Lysa', ter: 0.24, description: 'Robotrådgivare (inkl. fondavgifter)' },
  { name: 'Avanza Global', ter: 0.12, description: 'Global indexfond' },
];

const SPREAD_PCT = 0.002; // 0.2% average spread
const NUM_STOCKS = 10;

export function CostCalculator() {
  const [capital, setCapital] = useState(100000);
  const [strategy, setStrategy] = useState<keyof typeof STRATEGIES>('sammansatt_momentum');
  const [broker, setBroker] = useState<keyof typeof BROKERS>('avanza');
  const [years, setYears] = useState(10);

  const costs = useMemo((): CostBreakdown => {
    const strat = STRATEGIES[strategy];
    const brk = BROKERS[broker];
    
    // Per trade cost
    const tradeValue = capital / NUM_STOCKS;
    const courtagePerTrade = Math.max(brk.minFee, tradeValue * brk.pct);
    const spreadPerTrade = tradeValue * SPREAD_PCT / 2; // Half spread per trade
    
    // Per rebalance (turnover determines how many stocks change)
    const tradesPerRebalance = NUM_STOCKS * strat.turnover * 2; // Buy + sell
    const courtagePerRebalance = courtagePerTrade * tradesPerRebalance;
    const spreadPerRebalance = spreadPerTrade * tradesPerRebalance;
    const totalPerRebalance = courtagePerRebalance + spreadPerRebalance;
    
    // Annual costs
    const annualRebalanceCost = totalPerRebalance * strat.rebalancesPerYear;
    const totalAnnualCost = annualRebalanceCost;
    const costPct = (totalAnnualCost / capital) * 100;
    
    // Net return
    const netExpectedReturn = strat.expectedReturn - costPct;
    
    // Breakeven: where cost% < 2% (acceptable drag)
    const targetCostPct = 2;
    const breakevenCapital = Math.ceil((annualRebalanceCost / targetCostPct) * 100 / 1000) * 1000;
    
    return {
      courtage: courtagePerRebalance,
      spread: spreadPerRebalance,
      totalPerRebalance,
      annualRebalanceCost,
      totalAnnualCost,
      costPct,
      netExpectedReturn,
      isViable: costPct < 3,
      breakevenCapital,
    };
  }, [capital, strategy, broker]);

  // Compound growth calculation
  const compoundGrowth = useMemo(() => {
    const strat = STRATEGIES[strategy];
    const withCosts: number[] = [capital];
    const withoutCosts: number[] = [capital];
    const etfGrowth: number[] = [capital];
    
    const etfReturn = 8; // Assume 8% for index
    
    for (let y = 1; y <= years; y++) {
      withCosts.push(withCosts[y - 1] * (1 + (strat.expectedReturn - costs.costPct) / 100));
      withoutCosts.push(withoutCosts[y - 1] * (1 + strat.expectedReturn / 100));
      etfGrowth.push(etfGrowth[y - 1] * (1 + etfReturn / 100));
    }
    
    return { withCosts, withoutCosts, etfGrowth };
  }, [capital, strategy, costs.costPct, years]);

  const formatSEK = (n: number) => Math.round(n).toLocaleString('sv-SE');

  return (
    <div className={styles.card}>
      <h3 className={styles.cardTitle}>Kostnadsberäknare</h3>
      <p style={{ color: '#9ca3af', fontSize: '0.875rem', marginBottom: '16px' }}>
        Se verkliga kostnader för din investering
      </p>

      {/* Inputs */}
      <div style={{ display: 'grid', gap: '16px', marginBottom: '24px' }}>
        <div>
          <label style={{ display: 'block', color: '#d1d5db', fontSize: '0.875rem', marginBottom: '4px' }}>
            Investeringsbelopp: <strong>{formatSEK(capital)} kr</strong>
          </label>
          <input
            type="range"
            min={10000}
            max={1000000}
            step={10000}
            value={capital}
            onChange={(e) => setCapital(Number(e.target.value))}
            style={{ width: '100%' }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#6b7280' }}>
            <span>10 000 kr</span>
            <span>1 000 000 kr</span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
          <div>
            <label style={{ display: 'block', color: '#d1d5db', fontSize: '0.875rem', marginBottom: '4px' }}>Strategi</label>
            <NativeSelect.Root size="sm" w="100%">
              <NativeSelect.Field value={strategy} onChange={(e) => setStrategy(e.target.value as keyof typeof STRATEGIES)} bg="bg.muted" borderColor="border" color="fg">
                {Object.entries(STRATEGIES).map(([key, s]) => (
                  <option key={key} value={key}>{s.name}</option>
                ))}
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </div>
          <div>
            <label style={{ display: 'block', color: '#d1d5db', fontSize: '0.875rem', marginBottom: '4px' }}>Mäklare</label>
            <NativeSelect.Root size="sm" w="100%">
              <NativeSelect.Field value={broker} onChange={(e) => setBroker(e.target.value as keyof typeof BROKERS)} bg="bg.muted" borderColor="border" color="fg">
                {Object.entries(BROKERS).map(([key, b]) => (
                  <option key={key} value={key}>{b.name}</option>
                ))}
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </div>
        </div>
      </div>

      {/* Cost Breakdown */}
      <div style={{ background: '#1f2937', borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
        <h4 style={{ color: '#f3f4f6', fontWeight: '600', marginBottom: '12px' }}>Kostnadsuppdelning (årlig)</h4>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#9ca3af' }}>Courtage ({STRATEGIES[strategy].rebalancesPerYear}x ombalansering)</span>
            <span style={{ color: '#f3f4f6' }}>{formatSEK(costs.courtage * STRATEGIES[strategy].rebalancesPerYear)} kr</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#9ca3af' }}>Spread (köp/sälj-skillnad)</span>
            <span style={{ color: '#f3f4f6' }}>{formatSEK(costs.spread * STRATEGIES[strategy].rebalancesPerYear)} kr</span>
          </div>
          <div style={{ borderTop: '1px solid #374151', paddingTop: '8px', display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#f3f4f6', fontWeight: '600' }}>Total årlig kostnad</span>
            <span style={{ color: '#f59e0b', fontWeight: '600' }}>{formatSEK(costs.totalAnnualCost)} kr ({costs.costPct.toFixed(2)}%)</span>
          </div>
        </div>
      </div>

      {/* Viability Indicator */}
      <div style={{ 
        background: costs.isViable ? '#065f46' : '#7f1d1d', 
        padding: '12px', 
        borderRadius: '6px', 
        marginBottom: '16px' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.25rem', color: costs.isViable ? '#10b981' : '#f59e0b' }}>{costs.isViable ? '✓' : '!'}</span>
          <div>
            <div style={{ color: costs.isViable ? '#d1fae5' : '#fecaca', fontWeight: '600' }}>
              {costs.isViable ? 'Lönsamt' : 'Höga kostnader'}
            </div>
            <div style={{ color: costs.isViable ? '#a7f3d0' : '#fca5a5', fontSize: '0.875rem' }}>
              {costs.isViable 
                ? `Förväntad nettoavkastning: ${costs.netExpectedReturn.toFixed(1)}% per år`
                : `Minimikapital för denna strategi: ${formatSEK(costs.breakevenCapital)} kr`
              }
            </div>
          </div>
        </div>
      </div>

      {/* ETF Comparison */}
      <div style={{ marginBottom: '16px' }}>
        <h4 style={{ color: '#f3f4f6', fontWeight: '600', marginBottom: '12px' }}>Jämförelse med alternativ</h4>
        <div style={{ display: 'grid', gap: '8px' }}>
          {ETF_ALTERNATIVES.map((etf) => {
            const etfCost = capital * (etf.ter / 100);
            const strategyBetter = STRATEGIES[strategy].expectedReturn - costs.costPct > 8 - etf.ter;
            
            return (
              <div key={etf.name} style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                background: '#374151', 
                padding: '10px 12px', 
                borderRadius: '6px' 
              }}>
                <div>
                  <div style={{ color: '#f3f4f6', fontWeight: '500' }}>{etf.name}</div>
                  <div style={{ color: '#9ca3af', fontSize: '0.75rem' }}>{etf.description}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ color: '#f3f4f6' }}>{formatSEK(etfCost)} kr/år</div>
                  <div style={{ color: strategyBetter ? '#10b981' : '#ef4444', fontSize: '0.75rem' }}>
                    {strategyBetter ? 'Strategin bättre' : 'ETF billigare'}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Compound Effect */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h4 style={{ color: '#f3f4f6', fontWeight: '600' }}>Tillväxt över tid</h4>
          <NativeSelect.Root size="sm" w="auto">
            <NativeSelect.Field value={years} onChange={(e) => setYears(Number(e.target.value))} bg="bg.muted" borderColor="border" color="fg">
              <option value={5}>5 år</option>
              <option value={10}>10 år</option>
              <option value={20}>20 år</option>
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Med kostnader</div>
            <div style={{ fontWeight: 'bold', color: '#10b981' }}>{formatSEK(compoundGrowth.withCosts[years])} kr</div>
          </div>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Utan kostnader</div>
            <div style={{ fontWeight: 'bold', color: '#60a5fa' }}>{formatSEK(compoundGrowth.withoutCosts[years])} kr</div>
          </div>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Kostnad totalt</div>
            <div style={{ fontWeight: 'bold', color: '#f59e0b' }}>
              {formatSEK(compoundGrowth.withoutCosts[years] - compoundGrowth.withCosts[years])} kr
            </div>
          </div>
        </div>

        {/* Simple bar chart */}
        <div style={{ background: '#1f2937', borderRadius: '6px', padding: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', height: '100px', gap: '8px' }}>
            {[0, Math.floor(years / 2), years].map((y) => {
              const maxVal = compoundGrowth.withoutCosts[years];
              const withCostHeight = (compoundGrowth.withCosts[y] / maxVal) * 100;
              const etfHeight = (compoundGrowth.etfGrowth[y] / maxVal) * 100;
              
              return (
                <div key={y} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'flex-end', height: '80px' }}>
                    <div style={{ width: '20px', background: '#10b981', height: `${withCostHeight}%`, borderRadius: '2px 2px 0 0' }} title="Strategi" />
                    <div style={{ width: '20px', background: '#6b7280', height: `${etfHeight}%`, borderRadius: '2px 2px 0 0' }} title="Index" />
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '4px' }}>År {y}</div>
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', marginTop: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '12px', height: '12px', background: '#10b981', borderRadius: '2px' }} />
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Strategi</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <div style={{ width: '12px', height: '12px', background: '#6b7280', borderRadius: '2px' }} />
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Index (8%)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
