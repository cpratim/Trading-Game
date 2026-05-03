import { useState, useEffect } from 'react'

export default function OrderEntry({ prefill, onSubmit }) {
  const [side, setSide] = useState('buy')
  const [price, setPrice] = useState('')
  const [qty, setQty] = useState(1)

  useEffect(() => {
    if (!prefill) return
    setSide(prefill.side)
    setPrice(prefill.price)
  }, [prefill])

  const handleSubmit = () => {
    const p = parseFloat(price)
    const q = parseInt(qty)
    if (!p || !q || q <= 0) return
    onSubmit({ side, price: p, size: q })
  }

  const handleKey = (e) => {
    if (e.key === 'Enter') handleSubmit()
  }

  return (
    <div className="oe-wrap">
      <div className="oe-sides">
        <button
          className={`oe-btn bid ${side === 'buy' ? 'active' : ''}`}
          onClick={() => setSide('buy')}
        >BID</button>
        <button
          className={`oe-btn ask ${side === 'sell' ? 'active' : ''}`}
          onClick={() => setSide('sell')}
        >ASK</button>
      </div>

      <div className="oe-fields">
        <div className="oe-field">
          <label>Price</label>
          <input
            type="number"
            value={price}
            onChange={e => setPrice(e.target.value)}
            onKeyDown={handleKey}
            placeholder="0.00"
          />
        </div>
        <div className="oe-field">
          <label>Qty</label>
          <input
            type="number"
            min={1}
            value={qty}
            onChange={e => setQty(e.target.value)}
            onKeyDown={handleKey}
            placeholder="1"
          />
        </div>
      </div>

      <button
        className={`oe-submit ${side === 'buy' ? 'bid' : 'ask'}`}
        onClick={handleSubmit}
      >
        {side === 'buy' ? 'Place Bid' : 'Place Ask'}
      </button>
    </div>
  )
}
