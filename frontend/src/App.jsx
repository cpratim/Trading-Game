import { useState, useEffect, useCallback } from 'react'
import { Group as PanelGroup, Panel, Separator as PanelResizeHandle } from 'react-resizable-panels'
import { socket } from './socket'
import PriceChart from './components/PriceChart'
import OrderLadder from './components/OrderLadder'
import OrderEntry from './components/OrderEntry'
import MyOrders from './components/MyOrders'
import './App.css'

const MAX_TRADES = 300

export default function App() {
  const [connected, setConnected] = useState(false)
  const [trader, setTrader] = useState(null)
  const [book, setBook] = useState({ bids: [], asks: [] })
  const [trades, setTrades] = useState([])
  const [myOrders, setMyOrders] = useState({})
  const [position, setPosition] = useState({ qty: 0, avg_price: 0, realized: 0, unrealized: 0 })
  const [prefill, setPrefill] = useState(null)
  const [qty, setQty] = useState(1)
  const [midHistory, setMidHistory] = useState([])

  useEffect(() => {
    const onConnect = () => setConnected(true)
    const onDisconnect = () => setConnected(false)
    const onHello = (data) => setTrader(data)
    const onBook = (data) => {
      setBook(data)
      const bestBid = data.bids.length ? data.bids[0][0] : null
      const bestAsk = data.asks.length ? data.asks[0][0] : null
      if (bestBid != null && bestAsk != null) {
        const mid = (bestBid + bestAsk) / 2
        setMidHistory(prev => [...prev.slice(-299), { ts: Date.now() / 1000, mid }])
      }
    }
    const onTrade = (data) => setTrades(prev => [...prev.slice(-(MAX_TRADES - 1)), data])
    const onTradesHistory = (data) => setTrades(data.slice(-MAX_TRADES))
    const onPosition = (data) => setPosition(data)

    const onOrderAccepted = (data) => {
      setMyOrders(prev => ({
        ...prev,
        [data.order_id]: { ...data, filled: data.size - data.remaining },
      }))
    }

    const onFill = (data) => {
      setMyOrders(prev => {
        const order = prev[data.order_id]
        if (!order) return prev
        return {
          ...prev,
          [data.order_id]: {
            ...order,
            filled: order.size - data.remaining,
            remaining: data.remaining,
            status: data.remaining === 0 ? 'filled' : 'partial',
          },
        }
      })
    }

    const onOrderCanceled = (data) => {
      setMyOrders(prev => {
        const order = prev[data.order_id]
        if (!order) return prev
        return { ...prev, [data.order_id]: { ...order, status: 'cancelled' } }
      })
    }

    const onOrderRejected = (data) => {
      console.warn('[order_rejected]', data.reason, data)
    }

    socket.on('connect', onConnect)
    socket.on('disconnect', onDisconnect)
    socket.on('hello', onHello)
    socket.on('book', onBook)
    socket.on('trade', onTrade)
    socket.on('trades_history', onTradesHistory)
    socket.on('position', onPosition)
    socket.on('order_accepted', onOrderAccepted)
    socket.on('fill', onFill)
    socket.on('order_canceled', onOrderCanceled)
    socket.on('order_rejected', onOrderRejected)

    return () => {
      socket.off('connect', onConnect)
      socket.off('disconnect', onDisconnect)
      socket.off('hello', onHello)
      socket.off('book', onBook)
      socket.off('trade', onTrade)
      socket.off('trades_history', onTradesHistory)
      socket.off('position', onPosition)
      socket.off('order_accepted', onOrderAccepted)
      socket.off('fill', onFill)
      socket.off('order_canceled', onOrderCanceled)
      socket.off('order_rejected', onOrderRejected)
    }
  }, [])

  // Ladder click: place immediately with current qty, also sync the form
  const handleLadderSelect = useCallback((side, price) => {
    socket.emit('submit_order', { side, type: 'limit', price, size: qty })
    setPrefill({ side, price })
  }, [qty])

  const handleOrderSubmit = useCallback(({ side, price, size }) => {
    socket.emit('submit_order', { side, type: 'limit', price, size })
  }, [])

  const cancelOrder = useCallback((orderId) => {
    socket.emit('cancel_order', { order_id: orderId })
  }, [])

  // Compute my resting orders per price level for ladder overlay
  const myBidMap = {}
  const myAskMap = {}
  Object.values(myOrders).forEach(order => {
    if ((order.status === 'open' || order.status === 'partial') && order.price != null) {
      if (order.side === 'buy')
        myBidMap[order.price] = (myBidMap[order.price] || 0) + order.remaining
      else
        myAskMap[order.price] = (myAskMap[order.price] || 0) + order.remaining
    }
  })

  const pnl = position.realized + position.unrealized

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <span className="app-title">Trading Game</span>
          <span className={`conn-status ${connected ? 'on' : 'off'}`}>
            {connected ? '● live' : '○ disconnected'}
          </span>
          {trader && <span className="trader-name">{trader.name}</span>}
        </div>

        <div className="header-center">
          <span className="pos-item label">pos</span>
          <span className={`pos-item qty ${position.qty > 0 ? 'long' : position.qty < 0 ? 'short' : ''}`}>
            {position.qty > 0 ? '+' : ''}{position.qty}
          </span>
          <span className="pos-item label">avg</span>
          <span className="pos-item">{position.avg_price.toFixed(2)}</span>
          <span className="pos-item label">pnl</span>
          <span className={`pos-item pnl ${pnl >= 0 ? 'pos' : 'neg'}`}>
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
          </span>
        </div>
      </header>

      <PanelGroup direction="horizontal" className="main-group">
        <Panel defaultSize={75} minSize={40}>
          <PanelGroup direction="vertical">
            <Panel defaultSize={65} minSize={25}>
              <div className="chart-panel">
                <PriceChart trades={trades} midHistory={midHistory} />
              </div>
            </Panel>
            <PanelResizeHandle className="resize-handle-h" />
            <Panel defaultSize={35} minSize={15}>
              <div className="orders-panel">
                <MyOrders orders={myOrders} onCancel={cancelOrder} />
              </div>
            </Panel>
          </PanelGroup>
        </Panel>
        <PanelResizeHandle className="resize-handle-v" />
        <Panel defaultSize={25} minSize={18}>
          <div className="ladder-panel">
            <OrderEntry prefill={prefill} qty={qty} onQtyChange={setQty} onSubmit={handleOrderSubmit} />
            <OrderLadder book={book} myBidMap={myBidMap} myAskMap={myAskMap} onSelect={handleLadderSelect} />
          </div>
        </Panel>
      </PanelGroup>
    </div>
  )
}
