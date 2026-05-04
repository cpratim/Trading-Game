"""Trading game backend - Flask + SocketIO.

Run:    pip install -r requirements.txt && python app.py
Port:   5002

Inbound events:
  submit_order    {side: "buy"|"sell", type: "limit"|"market", price?: float, size: int}
  cancel_order    {order_id: int}

Outbound events:
  hello           {trader_id, name}                                   (private, on connect)
  open_orders     [{order_id, side, price, size, remaining, filled,
                    status, type}]                                     (private, on reconnect)
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
import os
import threading

from flask import Flask, request, send_from_directory
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
SERVE_FRONTEND = os.environ.get("SERVE_FRONTEND", "0") == "1"
DIST_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")

app = Flask(__name__, static_folder=DIST_DIR if SERVE_FRONTEND else None)
app.config["SECRET_KEY"] = "demo"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

if SERVE_FRONTEND:
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        file_path = os.path.join(DIST_DIR, path)
        if path and os.path.exists(file_path):
            return send_from_directory(DIST_DIR, path)
        return send_from_directory(DIST_DIR, "index.html")

book = OrderBook()
positions: dict[str, Position] = {MM_TRADER_ID: Position()}
names: dict[str, str] = {}          # trader_id -> display name
sid_to_trader: dict[str, str] = {}  # socket sid -> persistent trader_id
trader_to_sid: dict[str, str] = {}  # persistent trader_id -> current socket sid
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


def emit_position(trader_id: str):
    sid = trader_to_sid.get(trader_id)
    if not sid:
        return
    pos = positions.get(trader_id, Position())
    socketio.emit("position", {
        "qty": pos.qty,
        "avg_price": round(pos.avg_price, 4),
        "realized": round(pos.realized, 4),
        "unrealized": round(pos.unrealized(_last_price()), 4),
    }, to=sid)


def emit_all_positions():
    for trader_id in list(names.keys()):
        emit_position(trader_id)


def apply_trades(trades):
    for t in trades:
        positions.setdefault(t.buy_trader, Position()).apply_trade("buy", t.price, t.size)
        positions.setdefault(t.sell_trader, Position()).apply_trade("sell", t.price, t.size)
        emit_trade(t)


# --- socket handlers ------------------------------------------------------
@socketio.on("connect")
def on_connect():
    sid = request.sid
    trader_id = request.args.get("trader_id") or sid

    sid_to_trader[sid] = trader_id
    trader_to_sid[trader_id] = sid
    names[trader_id] = f"trader_{trader_id[:6]}"
    positions.setdefault(trader_id, Position())

    emit("hello", {"trader_id": trader_id, "name": names[trader_id]})
    emit("book", book.snapshot(depth=LEVELS))
    emit("trades_history", [
        {"price": t.price, "size": t.size, "ts": t.ts}
        for t in book.trades[-100:]
    ])
    emit_position(trader_id)

    # Restore any resting orders that survived the reconnect
    open_orders = [
        {
            "order_id": o.id,
            "side": o.side,
            "type": "limit",
            "price": o.price,
            "size": o.size,
            "remaining": o.remaining,
            "filled": o.size - o.remaining,
            "status": "open" if o.remaining == o.size else "partial",
            "fills": [],
        }
        for o in book.orders.values()
        if o.trader_id == trader_id
    ]
    if open_orders:
        emit("open_orders", open_orders)

    print(f"[connect] {names[trader_id]} ({trader_id[:8]})")


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    trader_id = sid_to_trader.pop(sid, sid)
    trader_to_sid.pop(trader_id, None)
    print(f"[disconnect] {names.get(trader_id, trader_id)}")


@socketio.on("submit_order")
def on_submit(data):
    sid = request.sid
    trader_id = sid_to_trader.get(sid, sid)

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
        order, trades = book.submit(trader_id, side, price, size, post_residual=post_residual)
        apply_trades(trades)
        emit_book()

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

        for t in trades:
            if t.aggressor == "buy":
                passive_trader, passive_oid, passive_side = (
                    t.sell_trader, t.sell_order_id, "sell")
            else:
                passive_trader, passive_oid, passive_side = (
                    t.buy_trader, t.buy_order_id, "buy")
            passive_sid = trader_to_sid.get(passive_trader)
            if not passive_sid:
                continue  # MM or disconnected
            resting = book.orders.get(passive_oid)
            socketio.emit("fill", {
                "order_id": passive_oid,
                "trade_id": t.id,
                "price": t.price,
                "size": t.size,
                "side": passive_side,
                "remaining": resting.remaining if resting else 0,
                "ts": t.ts,
            }, to=passive_sid)

    if trades:
        emit_all_positions()
    else:
        emit_position(trader_id)


@socketio.on("cancel_order")
def on_cancel(data):
    sid = request.sid
    trader_id = sid_to_trader.get(sid, sid)
    try:
        order_id = int(data["order_id"])
    except (KeyError, TypeError, ValueError):
        emit("order_rejected", {"reason": "invalid order_id"})
        return
    with lock:
        ok = book.cancel(order_id, trader_id)
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
    port = int(os.environ.get("PORT", 5002))
    print(f"Trading game backend listening on http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=False,
                 allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
