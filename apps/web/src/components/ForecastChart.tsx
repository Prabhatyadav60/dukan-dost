import { Bar, Cell, Line, ComposedChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts';
import type { Forecast } from '../api/types';
import { shortDate } from '../lib/dates';
import { formatPaise } from '../lib/money';
import { s } from '../strings';

/** Daily forecast bars (festival days in Paytm blue) over a dashed normal-day baseline. */
export function ForecastChart({ f }: { f: Forecast }) {
  const rows = f.daily.map((d) => ({
    label: shortDate(d.date),
    forecast: d.forecast_paise / 100,
    baseline: d.baseline_paise / 100,
    festive: d.uplift > 1,
  }));
  return (
    <div className="chartwrap">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 6, bottom: 0, left: 6 }}>
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#55657E' }} interval={1} tickLine={false} axisLine={{ stroke: '#DDE6F0' }} />
          <Tooltip
            formatter={(v: number, name: string) => [formatPaise(Math.round(v * 100)), name === 'baseline' ? s.forecast.baseline : 'Forecast']}
            contentStyle={{ borderRadius: 10, border: '1px solid #DDE6F0', fontSize: 13 }}
          />
          <Bar dataKey="forecast" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            {rows.map((r, i) => <Cell key={i} fill={r.festive ? '#00BAF2' : '#C5D3E3'} />)}
          </Bar>
          <Line dataKey="baseline" type="stepAfter" stroke="#002E6E" strokeDasharray="5 4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
