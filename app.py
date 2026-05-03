"""Trading game backend - Flask + SocketIO.

Run:    pip install -r requirements.txt && python app.py
Port:   5000

Inbound events:
  submit_order    {side: "buy"|"sell", type: "limit"|"market", price?: float, size: int}
  cancel_order    {order_id: int}

Outbound events:
  hello           {trader_id, name}                                   (private, on connect)
  book            {bids: [[p,sz], ...], asks: [[p,sz], ...]}          (broadcast)
  trade           {price, size, ts, aggressor}                        (broadcast tape)
  trades_history  [{price, size, ts}, ...]                            (private, on connect)
  position        {qty, avg_price, realized, unrealized}              (private)
  order_accepted  {order_id, side, type, price, size, remaining,
                   status: "open"|"partial"|"filled", fills: [...]}    (private, to submitter)
  fill            {order_id, trade_id, price, size, side, remaining,
                   ts}                                                 (private, to passive trader)
  order_canceled  {order_id}                                          (private, to canceler)
  order_rejected  {reason, order_id?}                                 (private)
"""
import threading

from flask import Flask, request
from flask_socketio import SocketIO, emit

from orderbook import OrderBook, Position
from mm import MarketMaker

# --- config ---------------------------------------------------------------
MM_TRADER_ID = "__mm__"
TICK = 1.0
INITIAL_MID = 100.0
LEVELS = 10
MM_SIZE = 20
MM_REFRESH_S = 0.5

# --- app + state ----------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "demo"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

book = OrderBook()
positions: dict[str, Position] = {MM_TRADER_ID: Position()}
names: dict[str, str] = {}  # sid -> display name (only humans)
lock = threading.Lock()


# --- helpers --------------------------------------------------------------
def _last_price() -> float:
    return book.trades[-1].price if book.trades else INITIAL_MID


def emit_book():
    socketio.emit("book", book.snapshot(depth=LEVELS))


def emit_trade(t):
    socketio.emit("trade", {
        "price": t.price, "size": t.size,
        "ts": t.ts, "aggressor": t.aggressor,
    })


def emit_position(sid: str):
    pos = positions.get(sid, Position())
    socketio.emit("position", {
        "qty": pos.qty,
        "avg_price": round(pos.avg_price, 4),
        "realized": round(pos.realized, 4),
        "unrealized": round(pos.unrealized(_last_price()), 4),
    }, to=sid)


def emit_all_positions():
    for sid in list(names.keys()):
        emit_position(sid)


def apply_trades(trades):
    for t in trades:
        positions.setdefault(t.buy_trader, Position()).apply_trade("buy", t.price, t.size)
        positions.setdefault(t.sell_trader, Position()).apply_trade("sell", t.price, t.size)
        emit_trade(t)


# --- socket handlers ------------------------------------------------------
@socketio.on("connect")
def on_connect():
    sid = request.sid
    names[sid] = f"trader_{sid[:6]}"
    positions.setdefault(sid, Position())
    emit("hello", {"trader_id": sid, "name": names[sid]})
    emit("book", book.snapshot(depth=LEVELS))
    emit("trades_history", [
        {"price": t.price, "size": t.size, "ts": t.ts}
        for t in book.trades[-100:]
    ])
    emit_position(sid)
    print(f"[connect] {names[sid]} ({sid})")


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    name = names.pop(sid, sid)
    print(f"[disconnect] {name}")


@socketio.on("submit_order")
def on_submit(data):
    sid = request.sid

    side = data.get("side")
    if side not in ("buy", "sell"):
        emit("order_rejected", {"reason": "invalid side"})
        return
    try:
        size = int(data.get("size", 0))
    except (TypeError, ValueError):
        emit("order_rejected", {"reason": "invalid size"})
        return
    if size <= 0:
        emit("order_rejected", {"reason": "size must be positive"})
        return

    order_type = data.get("type", "limit")
    if order_type == "market":
        price = float("inf") if side == "buy" else float("-inf")
        post_residual = False
    elif order_type == "limit":
        try:
            price = float(data["price"])
        except (KeyError, TypeError, ValueError):
            emit("order_rejected", {"reason": "invalid price"})
            return
        post_residual = True
    else:
        emit("order_rejected", {"reason": f"unknown order type {order_type!r}"})
        return

    with lock:
        order, trades = book.submit(sid, side, price, size, post_residual=post_residual)
        apply_trades(trades)
        emit_book()

        # Tell the submitter about their order and any fills it generated.
        socketio.emit("order_accepted", {
            "order_id": order.id,
            "side": order.side,
            "type": order_type,
            "price": None if order_type == "market" else order.price,
            "size": order.size,
            "remaining": order.remaining,
            "status": ("filled" if order.remaining == 0
                       else "partial" if trades else "open"),
            "fills": [
                {"trade_id": t.id, "price": t.price, "size": t.size, "ts": t.ts}
                for t in trades
            ],
        }, to=sid)

        # Tell each passive resting-order owner that their order was hit.
        for t in trades:
            if t.aggressor == "buy":
                passive_trader, passive_oid, passive_side = (
                    t.sell_trader, t.sell_order_id, "sell")
            else:
                passive_trader, passive_oid, passive_side = (
                    t.buy_trader, t.buy_order_id, "buy")
            if passive_trader not in names:
                continue  # MM or disconnected client
            resting = book.orders.get(passive_oid)
            socketio.emit("fill", {
                "order_id": passive_oid,
                "trade_id": t.id,
                "price": t.price,
                "size": t.size,
                "side": passive_side,
                "remaining": resting.remaining if resting else 0,
                "ts": t.ts,
            }, to=passive_trader)

    if trades:
        emit_all_positions()  # mark moved -> everyone's unrealized updated
    else:
        emit_position(sid)  # only this trader sees a change (resting order placed)


@socketio.on("cancel_order")
def on_cancel(data):
    sid = request.sid
    try:
        order_id = int(data["order_id"])
    except (KeyError, TypeError, ValueError):
        emit("order_rejected", {"reason": "invalid order_id"})
        return
    with lock:
        ok = book.cancel(order_id, sid)
    if ok:
        socketio.emit("order_canceled", {"order_id": order_id}, to=sid)
        emit_book()
    else:
        emit("order_rejected", {"reason": "cancel failed", "order_id": order_id})


# --- mm callbacks ---------------------------------------------------------
def on_mm_trades(trades):
    if not trades:
        return
    apply_trades(trades)
    emit_all_positions()


# --- entrypoint -----------------------------------------------------------
def main():
    mm = MarketMaker(
        book, lock,
        on_book_change=emit_book,
        on_trades=on_mm_trades,
        trader_id=MM_TRADER_ID,
        initial_mid=INITIAL_MID,
        tick=TICK,
        levels=LEVELS,
        size_per_level=MM_SIZE,
        refresh_interval=MM_REFRESH_S,
    )
    mm.start()
    print("Trading game backend listening on http://0.0.0.0:5002")
    socketio.run(app, host="0.0.0.0", port=5002, debug=False,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()