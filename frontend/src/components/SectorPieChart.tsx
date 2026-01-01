import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

interface SectorData {
  sector: string;
  weight: number;
}

interface Props {
  data: SectorData[];
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#ff7300'];

export function SectorPieChart({ data }: Props) {
  if (!data?.length) return <p>No sector data</p>;

  const chartData = data.map(d => ({ ...d, name: d.sector }));

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="weight"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={100}
            label={({ name, weight }: any) => `${name}: ${weight}%`}
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
