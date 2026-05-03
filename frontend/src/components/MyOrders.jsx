const STATUS_RANK = { open: 0, partial: 1, filled: 2, cancelled: 3 }

export default function MyOrders({ orders, onCancel }) {
  const list = Object.values(orders).sort(
    (a, b) => (STATUS_RANK[a.status] ?? 9) - (STATUS_RANK[b.status] ?? 9)
  )

  return (
    <div className="my-orders">
      <div className="panel-title">My Orders</div>
      {list.length === 0 ? (
        <div className="orders-empty">no orders yet — click the ladder to place</div>
      ) : (
        <table className="orders-table">
          <thead>
            <tr>
              <th>side</th>
              <th>price</th>
              <th>size</th>
              <th>filled</th>
              <th>status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {list.map(order => (
              <tr key={order.order_id} className={`order-row ${order.status}`}>
                <td className={`o-side ${order.side}`}>{order.side.toUpperCase()}</td>
                <td>{order.price ?? 'MKT'}</td>
                <td>{order.size}</td>
                <td>{order.filled ?? 0} / {order.size}</td>
                <td className={`o-status ${order.status}`}>{order.status}</td>
                <td>
                  {(order.status === 'open' || order.status === 'partial') && (
                    <button className="cancel-btn" onClick={() => onCancel(order.order_id)}>
                      cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
