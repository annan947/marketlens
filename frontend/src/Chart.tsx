import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend, BarChart, Bar } from 'recharts';
import { number } from './data';
const colors = ['#4de1bb', '#8495ff', '#f1b66f', '#69bfea'];
export default function Chart({ data, series, x = 'x', histogram = false }: {
  data: Record<string, string | number>[]; series: { key: string; name: string }[]; x?: string; histogram?: boolean;
}) {
  const axes = <><CartesianGrid stroke="#26303e" vertical={false} strokeDasharray="3 5" /><XAxis dataKey={x} stroke="#8c99ad" minTickGap={35} tick={{ fontSize: 11 }} /><YAxis stroke="#8c99ad" width={65} tick={{ fontSize: 11 }} tickFormatter={value => number(value)} domain={histogram ? [0, 'auto'] : ['auto', 'auto']} /><Tooltip contentStyle={{ background: '#151e2b', border: '1px solid #344254', borderRadius: 10, color: '#eef4ff' }} /><Legend /></>;
  return <div className="chart" role="img" aria-label={`${series.map(item => item.name).join(', ')} chart`}><ResponsiveContainer width="100%" height="100%">
    {histogram ? <BarChart data={data}>{axes}<Bar dataKey={series[0].key} name={series[0].name} fill={colors[0]} radius={[3, 3, 0, 0]} isAnimationActive={false} /></BarChart> :
      <LineChart data={data}>{axes}{series.map((item, i) => <Line key={item.key} dataKey={item.key} name={item.name} stroke={colors[i % colors.length]} dot={false} strokeWidth={i < 3 ? 2 : 1} isAnimationActive={false} />)}</LineChart>}
  </ResponsiveContainer></div>;
}
