import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

interface Props {
  data: number[];
  title?: string;
}

export function RollingSharpeChart({ data, title = "Rolling Sharpe Ratio (3M)" }: Props) {
  if (!data?.length) return <p>No rolling data</p>;

  const chartData = data.map((v, i) => ({ idx: i, sharpe: v }));

  return (
    <div>
      <h4 style={{ margin: '0 0 0.5rem 0' }}>{title}</h4>
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="idx" hide />
            <YAxis domain={[-2, 3]} />
            <Tooltip formatter={(v: any) => v.toFixed(2)} />
            <ReferenceLine y={0} stroke="#888" />
            <ReferenceLine y={1} stroke="#22c55e" strokeDasharray="5 5" />
            <Line type="monotone" dataKey="sharpe" stroke="#8884d8" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
