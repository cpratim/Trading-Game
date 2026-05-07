"""Order book with price-time priority matching, plus position tracking."""
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import count
import time

_order_id = count(1)
_trade_id = count(1)


@dataclass
class Order:
    id: int
    trader_id: str
    side: str  # "buy" or "sell"
    price: float
    size: int
    remaining: int


@dataclass
class Trade:
    id: int
    price: float
    size: int
    ts: float
    aggressor: str  # "buy" or "sell"
    buy_trader: str
    sell_trader: str
    buy_order_id: int
    sell_order_id: int


STARTING_CASH = 0.0
POSITION_LIMIT = 1000


@dataclass
class Position:
    qty: int = 0          # signed: + long, - short
    avg_price: float = 0.0
    realized: float = 0.0
    cash: float = STARTING_CASH

    def apply_trade(self, side: str, price: float, size: int) -> None:
        # Cash flow
        if side == "buy":
            self.cash -= price * size
        else:
            self.cash += price * size

        signed = size if side == "buy" else -size
        new_qty = self.qty + signed
        if self.qty == 0:
            self.avg_price = price
        elif (self.qty > 0) == (signed > 0):
            self.avg_price = (self.avg_price * self.qty + price * signed) / new_qty
        else:
            close = min(abs(signed), abs(self.qty))
            pnl = (price - self.avg_price) * close if self.qty > 0 \
                else (self.avg_price - price) * close
            self.realized += pnl
            if (self.qty > 0 and new_qty < 0) or (self.qty < 0 and new_qty > 0):
                self.avg_price = price
            elif new_qty == 0:
                self.avg_price = 0.0
        self.qty = new_qty

    def pnl(self, mark: float) -> float:
        return self.cash + self.qty * mark - STARTING_CASH


class OrderBook:
    def __init__(self):
        self.bids: dict[float, deque[Order]] = defaultdict(deque)
        self.asks: dict[float, deque[Order]] = defaultdict(deque)
        self.orders: dict[int, Order] = {}
        self.trades: list[Trade] = []

    def best_bid(self):
        active = [p for p, q in self.bids.items() if q]
        return max(active) if active else None

    def best_ask(self):
        active = [p for p, q in self.asks.items() if q]
        return min(active) if active else None

    def _match(self, incoming: Order) -> list[Trade]:
        out: list[Trade] = []
        if incoming.side == "buy":
            opp = self.asks
            def best_fn():
                return min((p for p, q in opp.items() if q and p <= incoming.price), default=None)
        else:
            opp = self.bids
            def best_fn():
                return max((p for p, q in opp.items() if q and p >= incoming.price), default=None)

        while incoming.remaining > 0:
            level_price = best_fn()
            if level_price is None:
                break
            level_q = opp[level_price]
            resting = level_q[0]
            fill = min(incoming.remaining, resting.remaining)
            buy_t = incoming.trader_id if incoming.side == "buy" else resting.trader_id
            sell_t = incoming.trader_id if incoming.side == "sell" else resting.trader_id
            buy_oid = incoming.id if incoming.side == "buy" else resting.id
            sell_oid = incoming.id if incoming.side == "sell" else resting.id
            t = Trade(
                id=next(_trade_id),
                price=level_price,
                size=fill,
                ts=time.time(),
                aggressor=incoming.side,
                buy_trader=buy_t,
                sell_trader=sell_t,
                buy_order_id=buy_oid,
                sell_order_id=sell_oid,
            )
            out.append(t)
            self.trades.append(t)
            incoming.remaining -= fill
            resting.remaining -= fill
            if resting.remaining == 0:
                level_q.popleft()
                self.orders.pop(resting.id, None)
        return out

    def submit(self, trader_id: str, side: str, price: float, size: int,
               post_residual: bool = True) -> tuple[Order, list[Trade]]:
        """Submit a limit order. Marketable orders cross immediately.
        For a market order: pass +inf (buy) or -inf (sell) and post_residual=False.
        """
        order = Order(next(_order_id), trader_id, side, price, size, size)
        trades = self._match(order)
        is_marketable_sentinel = price in (float("inf"), float("-inf"))
        if order.remaining > 0 and post_residual and not is_marketable_sentinel:
            book = self.bids if side == "buy" else self.asks
            book[price].append(order)
            self.orders[order.id] = order
        return order, trades

    def cancel(self, order_id: int, trader_id: str) -> bool:
        order = self.orders.get(order_id)
        if order is None or order.trader_id != trader_id:
            return False
        book = self.bids if order.side == "buy" else self.asks
        try:
            book[order.price].remove(order)
        except ValueError:
            return False
        self.orders.pop(order_id, None)
        return True

    def reset(self):
        self.bids.clear()
        self.asks.clear()
        self.orders.clear()
        self.trades.clear()

    def snapshot(self, depth: int = 10) -> dict:
        bids = sorted((p for p, q in self.bids.items() if q), reverse=True)[:depth]
        asks = sorted(p for p, q in self.asks.items() if q)[:depth]
        return {
            "bids": [[p, sum(o.remaining for o in self.bids[p])] for p in bids],
            "asks": [[p, sum(o.remaining for o in self.asks[p])] for p in asks],
        }