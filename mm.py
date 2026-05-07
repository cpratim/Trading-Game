"""Synthetic market maker. Posts liquidity around a drifting mid price.

The MM:
- Seeds N levels each side at startup
- Every refresh tick, drifts mid by +/- 1 tick (random walk) and:
  - cancels its own orders that are outside the new target band
  - tops up size at each target level (without crossing)
"""
import random
import threading
import time
from typing import Callable


class MarketMaker:
    def __init__(self, book, lock,
                 on_book_change: Callable[[], None],
                 on_trades: Callable[[list], None],
                 trader_id: str = "__mm__",
                 initial_mid: float = 100.0,
                 tick: float = 1.0,
                 levels: int = 10,
                 size_per_level: int = 20,
                 refresh_interval: float = 0.5):
        self.book = book
        self.lock = lock
        self.on_book_change = on_book_change
        self.on_trades = on_trades
        self.trader_id = trader_id
        self.mid = initial_mid
        self.tick = tick
        self.levels = levels
        self.size = size_per_level
        self.interval = refresh_interval
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread = None

    @staticmethod
    def _r(x: float) -> float:
        # Round to kill float drift from repeated additions.
        return round(x, 6)

    def start(self):
        with self.lock:
            self._seed()
        self.on_book_change()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def pause(self):
        self._paused.set()
        with self.lock:
            for oid in list(self.book.orders.keys()):
                o = self.book.orders.get(oid)
                if o and o.trader_id == self.trader_id:
                    self.book.cancel(oid, self.trader_id)

    def resume(self):
        self._paused.clear()
        with self.lock:
            self._seed()
        self.on_book_change()

    def _seed(self):
        for i in range(1, self.levels + 1):
            self.book.submit(self.trader_id, "buy",
                             self._r(self.mid - i * self.tick), self.size)
            self.book.submit(self.trader_id, "sell",
                             self._r(self.mid + i * self.tick), self.size)

    def _run(self):
        while not self._stop.is_set():
            time.sleep(self.interval)
            if self._paused.is_set():
                continue
            trades = []
            with self.lock:
                self.mid = self._r(self.mid + random.choice([-self.tick, 0.0, self.tick]))
                trades = self._refresh()
            if trades:
                self.on_trades(trades)
            self.on_book_change()

    def _refresh(self) -> list:
        target_bids = {self._r(self.mid - i * self.tick) for i in range(1, self.levels + 1)}
        target_asks = {self._r(self.mid + i * self.tick) for i in range(1, self.levels + 1)}

        # Cancel my orders that are out-of-band.
        for oid, o in list(self.book.orders.items()):
            if o.trader_id != self.trader_id:
                continue
            target = target_bids if o.side == "buy" else target_asks
            if o.price not in target:
                self.book.cancel(oid, self.trader_id)

        all_trades = []
        # Top up bids.
        for p in target_bids:
            best_ask = self.book.best_ask()
            if best_ask is not None and p >= best_ask:
                continue  # would cross; skip
            current = sum(o.remaining for o in self.book.bids[p]
                          if o.trader_id == self.trader_id)
            if current < self.size:
                _, ts = self.book.submit(self.trader_id, "buy", p, self.size - current)
                all_trades.extend(ts)
        # Top up asks.
        for p in target_asks:
            best_bid = self.book.best_bid()
            if best_bid is not None and p <= best_bid:
                continue
            current = sum(o.remaining for o in self.book.asks[p]
                          if o.trader_id == self.trader_id)
            if current < self.size:
                _, ts = self.book.submit(self.trader_id, "sell", p, self.size - current)
                all_trades.extend(ts)
        return all_trades