import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

export default function PriceChart({ trades }) {
  const data = trades.map(t => ({
    time: new Date(t.ts * 1000).toLocaleTimeString(),
    price: t.price,
  }))

  const prices = trades.map(t => t.price)
  const min = prices.length ? Math.min(...prices) : 90
  const max = prices.length ? Math.max(...prices) : 110
  const pad = Math.max((max - min) * 0.15, 2)
  const last = prices.length ? prices[prices.length - 1] : null

  return (
    <div className="chart-wrap">
      <div className="panel-title">Price · last {last !== null ? last.toFixed(2) : '—'}</div>
      <ResponsiveContainer width="100%" height="90%">
        <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4ade80" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#4ade80" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="time"
            tick={{ fill: '#555', fontSize: 10 }}
            interval="preserveStartEnd"
            tickLine={false}
            axisLine={{ stroke: '#222' }}
          />
          <YAxis
            domain={[min - pad, max + pad]}
            tick={{ fill: '#555', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            width={42}
          />
          <Tooltip
            contentStyle={{ background: '#111122', border: '1px solid #2a2a4a', color: '#e0e0e0', fontSize: 12 }}
            labelStyle={{ color: '#666' }}
            formatter={v => [v.toFixed(2), 'price']}
          />
          {last !== null && (
            <ReferenceLine y={last} stroke="#4ade80" strokeDasharray="3 3" strokeOpacity={0.4} />
          )}
          <Area
            type="monotone"
            dataKey="price"
            stroke="#4ade80"
            strokeWidth={1.5}
            fill="url(#priceGrad)"
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
