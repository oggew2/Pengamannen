import { useState } from 'react';
import styles from '../styles/App.module.css';

interface QuizResult {
  strategy: string;
  strategyName: string;
  reasoning: string;
  minCapital: number;
  warnings: string[];
}

const STRATEGIES = {
  sammansatt_momentum: {
    name: 'Sammansatt Momentum',
    minCapital: 100000,
    rebalance: 'Kvartalsvis (4x/år)',
    expectedReturn: '15-20%',
    maxDrawdown: '-40%',
    timeCommitment: 'Medel',
  },
  trendande_varde: {
    name: 'Trendande Värde',
    minCapital: 50000,
    rebalance: 'Årligen (1x/år)',
    expectedReturn: '12-18%',
    maxDrawdown: '-35%',
    timeCommitment: 'Låg',
  },
  trendande_utdelning: {
    name: 'Trendande Utdelning',
    minCapital: 50000,
    rebalance: 'Årligen (1x/år)',
    expectedReturn: '10-15%',
    maxDrawdown: '-30%',
    timeCommitment: 'Låg',
  },
  trendande_kvalitet: {
    name: 'Trendande Kvalitet',
    minCapital: 50000,
    rebalance: 'Årligen (1x/år)',
    expectedReturn: '12-16%',
    maxDrawdown: '-30%',
    timeCommitment: 'Låg',
  },
};

export function StrategyQuiz() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({
    capital: 0,
    riskTolerance: 0,
    timeCommitment: '',
    goal: '',
  });
  const [result, setResult] = useState<QuizResult | null>(null);

  const questions = [
    {
      question: 'Hur mycket kapital planerar du att investera?',
      options: [
        { label: 'Under 50 000 kr', value: 25000 },
        { label: '50 000 - 100 000 kr', value: 75000 },
        { label: '100 000 - 300 000 kr', value: 200000 },
        { label: 'Över 300 000 kr', value: 500000 },
      ],
      key: 'capital',
    },
    {
      question: 'Hur stor nedgång kan du hantera utan att sälja?',
      options: [
        { label: 'Max 15% - Jag vill sova gott', value: 1 },
        { label: 'Max 25% - Jag tål lite svängningar', value: 2 },
        { label: 'Max 35% - Jag är långsiktig', value: 3 },
        { label: '40%+ - Jag köper mer vid nedgångar', value: 4 },
      ],
      key: 'riskTolerance',
    },
    {
      question: 'Hur ofta vill du ombalansera portföljen?',
      options: [
        { label: 'Så sällan som möjligt (1x/år)', value: 'annual' },
        { label: 'Kvartalsvis är ok (4x/år)', value: 'quarterly' },
      ],
      key: 'timeCommitment',
    },
    {
      question: 'Vad är viktigast för dig?',
      options: [
        { label: 'Högsta möjliga avkastning', value: 'growth' },
        { label: 'Stabil utdelning/kassaflöde', value: 'income' },
        { label: 'Balans mellan tillväxt och stabilitet', value: 'balanced' },
      ],
      key: 'goal',
    },
  ];

  const handleAnswer = (key: string, value: number | string) => {
    const newAnswers = { ...answers, [key]: value };
    setAnswers(newAnswers);

    if (step < questions.length - 1) {
      setStep(step + 1);
    } else {
      calculateResult(newAnswers);
    }
  };

  const calculateResult = (ans: typeof answers) => {
    const warnings: string[] = [];
    let strategy = 'trendande_varde';
    let reasoning = '';

    // Capital check
    if (ans.capital < 50000) {
      warnings.push('Med under 50 000 kr blir transaktionskostnaderna höga. Överväg en indexfond som Avanza Zero tills du sparat ihop mer.');
    }

    // Decision logic
    if (ans.timeCommitment === 'quarterly' && ans.riskTolerance >= 3 && ans.capital >= 100000) {
      strategy = 'sammansatt_momentum';
      reasoning = 'Du har tillräckligt kapital, hög risktolerans och är villig att ombalansera kvartalsvis. Momentum-strategin har historiskt gett högst avkastning.';
    } else if (ans.goal === 'income') {
      strategy = 'trendande_utdelning';
      reasoning = 'Du prioriterar utdelningar och kassaflöde. Utdelningsstrategin ger stabila utbetalningar med lägre volatilitet.';
    } else if (ans.riskTolerance <= 2) {
      strategy = 'trendande_kvalitet';
      reasoning = 'Du föredrar lägre risk. Kvalitetsstrategin investerar i stabila bolag med stark lönsamhet och lägre svängningar.';
    } else {
      strategy = 'trendande_varde';
      reasoning = 'Värdestrategin ger bra balans mellan avkastning och risk, med endast årlig ombalansering.';
    }

    // Capital warnings
    const minCapital = STRATEGIES[strategy as keyof typeof STRATEGIES].minCapital;
    if (ans.capital < minCapital) {
      warnings.push(`Rekommenderat minimikapital för ${STRATEGIES[strategy as keyof typeof STRATEGIES].name} är ${minCapital.toLocaleString('sv-SE')} kr.`);
    }

    setResult({
      strategy,
      strategyName: STRATEGIES[strategy as keyof typeof STRATEGIES].name,
      reasoning,
      minCapital,
      warnings,
    });
  };

  const reset = () => {
    setStep(0);
    setAnswers({ capital: 0, riskTolerance: 0, timeCommitment: '', goal: '' });
    setResult(null);
  };

  if (result) {
    const strategyInfo = STRATEGIES[result.strategy as keyof typeof STRATEGIES];
    return (
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Din rekommenderade strategi</h3>
        
        <div style={{ background: '#065f46', padding: '16px', borderRadius: '8px', marginBottom: '16px' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#d1fae5' }}>
            {result.strategyName}
          </div>
          <p style={{ color: '#a7f3d0', marginTop: '8px', fontSize: '0.875rem' }}>
            {result.reasoning}
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginBottom: '16px' }}>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Förväntad avkastning</div>
            <div style={{ fontWeight: 'bold', color: '#10b981' }}>{strategyInfo.expectedReturn}</div>
          </div>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Max nedgång</div>
            <div style={{ fontWeight: 'bold', color: '#ef4444' }}>{strategyInfo.maxDrawdown}</div>
          </div>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Ombalansering</div>
            <div style={{ fontWeight: 'bold', color: '#f3f4f6' }}>{strategyInfo.rebalance}</div>
          </div>
          <div style={{ background: '#374151', padding: '12px', borderRadius: '6px' }}>
            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Minimikapital</div>
            <div style={{ fontWeight: 'bold', color: '#f3f4f6' }}>{strategyInfo.minCapital.toLocaleString('sv-SE')} kr</div>
          </div>
        </div>

        {result.warnings.length > 0 && (
          <div style={{ background: '#78350f', padding: '12px', borderRadius: '6px', marginBottom: '16px' }}>
            <div style={{ fontWeight: 'bold', color: '#fcd34d', marginBottom: '4px' }}>⚠️ Tänk på</div>
            {result.warnings.map((w, i) => (
              <p key={i} style={{ color: '#fef3c7', fontSize: '0.875rem', marginTop: '4px' }}>{w}</p>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', gap: '12px' }}>
          <button onClick={reset} className={styles.btn} style={{ flex: 1 }}>
            Gör om testet
          </button>
          <a href={`/strategies/${result.strategy.replace('_', '-')}`} className={styles.btn} style={{ flex: 1, background: '#0d9488', textAlign: 'center' }}>
            Se strategin →
          </a>
        </div>
      </div>
    );
  }

  const currentQ = questions[step];
  const progress = ((step + 1) / questions.length) * 100;

  return (
    <div className={styles.card}>
      <h3 className={styles.cardTitle}>Hitta rätt strategi för dig</h3>
      
      <div style={{ background: '#374151', borderRadius: '4px', height: '8px', marginBottom: '16px' }}>
        <div style={{ background: '#0d9488', borderRadius: '4px', height: '100%', width: `${progress}%`, transition: 'width 300ms' }} />
      </div>
      
      <p style={{ color: '#9ca3af', fontSize: '0.875rem', marginBottom: '8px' }}>
        Fråga {step + 1} av {questions.length}
      </p>
      
      <h4 style={{ fontSize: '1.125rem', fontWeight: '600', color: '#f3f4f6', marginBottom: '16px' }}>
        {currentQ.question}
      </h4>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {currentQ.options.map((opt) => (
          <button
            key={String(opt.value)}
            onClick={() => handleAnswer(currentQ.key, opt.value)}
            style={{
              padding: '12px 16px',
              background: '#374151',
              border: '1px solid #4b5563',
              borderRadius: '6px',
              color: '#f3f4f6',
              textAlign: 'left',
              cursor: 'pointer',
              transition: 'all 150ms',
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.borderColor = '#0d9488';
              e.currentTarget.style.background = '#1f2937';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.borderColor = '#4b5563';
              e.currentTarget.style.background = '#374151';
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {step > 0 && (
        <button
          onClick={() => setStep(step - 1)}
          style={{ marginTop: '16px', color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          ← Tillbaka
        </button>
      )}
    </div>
  );
}
