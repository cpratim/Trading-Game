import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

const VISIBLE = 120

export default function PriceChart({ trades, midHistory }) {
  // Merge mid-price history and trade points into one timeline keyed by ts
  const tradeMap = Object.fromEntries(trades.map(t => [t.ts.toFixed(2), t.price]))

  const data = midHistory.slice(-VISIBLE).map(m => ({
    time: new Date(m.ts * 1000).toLocaleTimeString(),
    mid: m.mid,
    trade: tradeMap[m.ts.toFixed(2)] ?? null,
  }))

  const allPrices = [
    ...midHistory.slice(-VISIBLE).map(m => m.mid),
    ...trades.slice(-VISIBLE).map(t => t.price),
  ]
  const min = allPrices.length ? Math.min(...allPrices) : 90
  const max = allPrices.length ? Math.max(...allPrices) : 110
  const pad = Math.max((max - min) * 0.2, 1)

  const lastMid = midHistory.length ? midHistory[midHistory.length - 1].mid : null
  const lastTrade = trades.length ? trades[trades.length - 1].price : null

  return (
    <div className="chart-wrap">
      <div className="panel-title">
        Market
        <span className="chart-meta">
          {lastMid != null && <> · mid <strong>{lastMid.toFixed(2)}</strong></>}
          {lastTrade != null && <> · last trade <strong>{lastTrade.toFixed(2)}</strong></>}
          {trades.length > 0 && <> · {trades.length} trades</>}
        </span>
      </div>
      {data.length === 0 ? (
        <div className="chart-empty">
          Connecting to market…
        </div>
      ) : (
        <ResponsiveContainer width="100%" height="90%">
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
            <defs>
              <linearGradient id="midGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#60a5fa" stopOpacity={0} />
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
              formatter={(v, name) => [v?.toFixed(2) ?? '—', name]}
            />
            {lastMid != null && (
              <ReferenceLine y={lastMid} stroke="#60a5fa" strokeDasharray="3 3" strokeOpacity={0.3} />
            )}
            {/* Mid-price: continuous blue line */}
            <Area
              type="monotone"
              dataKey="mid"
              stroke="#60a5fa"
              strokeWidth={1.5}
              fill="url(#midGrad)"
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
            {/* Trade prices: green dots */}
            <Line
              type="monotone"
              dataKey="trade"
              stroke="#4ade80"
              strokeWidth={0}
              dot={{ r: 3, fill: '#4ade80', strokeWidth: 0 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
              connectNulls={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
