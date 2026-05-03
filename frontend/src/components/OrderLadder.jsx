export default function OrderLadder({ book, myBidMap = {}, myAskMap = {}, onSelect }) {
  const { bids = [], asks = [] } = book

  const bidMap = Object.fromEntries(bids.map(([p, s]) => [p, s]))
  const askMap = Object.fromEntries(asks.map(([p, s]) => [p, s]))

  const askPrices = asks.map(([p]) => p).sort((a, b) => b - a)
  const bidPrices = bids.map(([p]) => p).sort((a, b) => b - a)

  const maxQty = Math.max(...bids.map(([, s]) => s), ...asks.map(([, s]) => s), 1)

  const bestBid = bids.length ? bids[0][0] : null
  const bestAsk = asks.length ? asks[0][0] : null
  const spread = bestBid != null && bestAsk != null ? (bestAsk - bestBid).toFixed(2) : null

  // Ask row: [market ask qty] | price | [my ask qty]
  const renderAskRow = (price) => {
    const mktQty = askMap[price] || 0
    const myQty = myAskMap[price] || 0
    const pct = Math.round((mktQty / maxQty) * 100)

    return (
      <tr key={`ask-${price}`} className="ladder-row">
        <td
          className="l-qty l-mkt-ask"
          style={{ background: `linear-gradient(to left, rgba(255,107,107,0.18) ${pct}%, transparent ${pct}%)` }}
          onClick={() => onSelect('buy', price)}
        >
          {mktQty || ''}
        </td>
        <td className="l-price ask">{price}</td>
        <td className="l-qty l-mine" onClick={() => onSelect('sell', price)}>
          {myQty ? <span className="my-qty ask">{myQty}</span> : ''}
        </td>
      </tr>
    )
  }

  // Bid row: [my bid qty] | price | [market bid qty]
  const renderBidRow = (price) => {
    const mktQty = bidMap[price] || 0
    const myQty = myBidMap[price] || 0
    const pct = Math.round((mktQty / maxQty) * 100)

    return (
      <tr key={`bid-${price}`} className="ladder-row">
        <td className="l-qty l-mine" onClick={() => onSelect('buy', price)}>
          {myQty ? <span className="my-qty bid">{myQty}</span> : ''}
        </td>
        <td className="l-price bid">{price}</td>
        <td
          className="l-qty l-mkt-bid"
          style={{ background: `linear-gradient(to right, rgba(74,222,128,0.18) ${pct}%, transparent ${pct}%)` }}
          onClick={() => onSelect('sell', price)}
        >
          {mktQty || ''}
        </td>
      </tr>
    )
  }

  return (
    <div className="ladder">
      <div className="panel-title">Order Book</div>
      <table className="ladder-table">
        <thead>
          <tr>
            <th className="th-ask-mkt">qty</th>
            <th>price</th>
            <th className="th-bid-mkt">qty</th>
          </tr>
          <tr className="thead-sub">
            <th className="th-ask-mkt">market</th>
            <th></th>
            <th className="th-bid-mkt">market</th>
          </tr>
        </thead>
        <tbody>
          {askPrices.map(p => renderAskRow(p))}
          <tr className="spread-row">
            <td colSpan={3}>{spread != null ? `spread  ${spread}` : '—'}</td>
          </tr>
          {bidPrices.map(p => renderBidRow(p))}
        </tbody>
      </table>
    </div>
  )
}
