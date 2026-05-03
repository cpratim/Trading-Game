export default function OrderLadder({ book, onSelect }) {
  const { bids = [], asks = [] } = book

  // asks: backend gives ascending; reverse so highest ask is at top
  const askRows = [...asks].reverse()
  // bids: backend gives descending (highest bid first, closest to spread)
  const bidRows = bids

  const allSizes = [...asks.map(([, s]) => s), ...bids.map(([, s]) => s)]
  const maxSize = allSizes.length ? Math.max(...allSizes) : 1

  const spread = asks.length && bids.length
    ? (asks[0][0] - bids[0][0]).toFixed(2)
    : null

  const Row = ({ price, size, side }) => {
    const pct = Math.round((size / maxSize) * 100)
    const bg = side === 'ask'
      ? `linear-gradient(to left, rgba(248,113,113,0.18) ${pct}%, transparent ${pct}%)`
      : `linear-gradient(to right, rgba(74,222,128,0.18) ${pct}%, transparent ${pct}%)`

    return (
      <tr
        className={`ladder-row ${side}`}
        style={{ background: bg }}
        onClick={() => onSelect('buy', price)}
        onContextMenu={e => { e.preventDefault(); onSelect('sell', price) }}
      >
        <td className="l-size">{side === 'ask' ? size : ''}</td>
        <td className={`l-price ${side}`}>{price}</td>
        <td className="l-size">{side === 'bid' ? size : ''}</td>
      </tr>
    )
  }

  return (
    <div className="ladder">
      <div className="panel-title">Order Book</div>
      <div className="ladder-hint">left click = buy · right click = sell</div>
      <table className="ladder-table">
        <thead>
          <tr>
            <th>qty</th>
            <th>price</th>
            <th>qty</th>
          </tr>
        </thead>
        <tbody>
          {askRows.map(([price, size]) => (
            <Row key={`ask-${price}`} price={price} size={size} side="ask" />
          ))}
          <tr className="spread-row">
            <td colSpan={3}>
              {spread !== null ? `spread  ${spread}` : '—'}
            </td>
          </tr>
          {bidRows.map(([price, size]) => (
            <Row key={`bid-${price}`} price={price} size={size} side="bid" />
          ))}
        </tbody>
      </table>
    </div>
  )
}
