import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface Props {
  data: { date: string; value: number }[];
  maxDrawdown?: number;
  currentDrawdown?: number;
}

export function DrawdownChart({ data, maxDrawdown, currentDrawdown }: Props) {
  if (!data?.length) return <p>No drawdown data</p>;

  // Calculate drawdown from peak
  let peak = data[0]?.value || 0;
  const chartData = data.map(d => {
    if (d.value > peak) peak = d.value;
    const dd = ((d.value - peak) / peak) * 100;
    return { date: d.date, value: d.value, drawdown: Math.round(dd * 100) / 100 };
  });

  return (
    <div>
      <div style={{ display: 'flex', gap: '2rem', marginBottom: '1rem' }}>
        <div>
          <span style={{ color: '#888' }}>Max Drawdown: </span>
          <strong style={{ color: '#ef4444' }}>{maxDrawdown?.toFixed(1)}%</strong>
        </div>
        <div>
          <span style={{ color: '#888' }}>Current: </span>
          <strong style={{ color: currentDrawdown && currentDrawdown < -5 ? '#ef4444' : '#22c55e' }}>
            {currentDrawdown?.toFixed(1)}%
          </strong>
        </div>
      </div>
      <div style={{ width: '100%', height: 250 }}>
        <ResponsiveContainer>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis domain={['auto', 0]} tickFormatter={v => `${v}%`} />
            <Tooltip formatter={(v: any) => `${v}%`} />
            <ReferenceLine y={0} stroke="#888" />
            <Line type="monotone" dataKey="drawdown" stroke="#ef4444" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
