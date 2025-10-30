"""
order book implementation for maintaining limit order book state
"""

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


@dataclass
class Order:
    """represents a single order in the book"""

    order_id: str
    side: str  # 'buy' or 'sell'
    price: Decimal
    size: Decimal
    timestamp: int


@dataclass
class Fill:
    """represents a fill event from matching orders"""

    taker_order_id: str
    maker_order_id: str
    price: Decimal
    size: Decimal
    timestamp: int


class OrderBook:
    """maintains the current state of the limit order book"""

    def __init__(self):
        # price level -> list of orders at that price
        self.bids: Dict[Decimal, List[Order]] = {}
        self.asks: Dict[Decimal, List[Order]] = {}
        # order_id -> (side, price) for quick lookup
        self.order_map: Dict[str, Tuple[str, Decimal]] = {}

    def insert(self, order: Order) -> List[Fill]:
        """
        insert a new order into the book

        returns list of fills if the order was matched
        """
        if order.side not in ["buy", "sell"]:
            raise ValueError(f"invalid order side: {order.side}")

        fills = []

        # try to match the order
        if order.side == "buy":
            fills = self._match_buy(order)
        else:
            fills = self._match_sell(order)

        # if order still has size, add to book
        if order.size > 0:
            self._add_to_book(order)

        return fills

    def cancel(self, order_id: str) -> Optional[Order]:
        """
        cancel an existing order

        returns the cancelled order if found, None otherwise
        """
        if order_id not in self.order_map:
            return None

        side, price = self.order_map[order_id]
        book = self.bids if side == "buy" else self.asks

        # find and remove the order
        if price in book:
            for i, order in enumerate(book[price]):
                if order.order_id == order_id:
                    cancelled = book[price].pop(i)
                    if not book[price]:  # remove empty price level
                        del book[price]
                    del self.order_map[order_id]
                    return cancelled

        return None

    def _match_buy(self, order: Order) -> List[Fill]:
        """match a buy order against the ask side"""
        fills = []
        ask_prices = sorted(self.asks.keys())

        for price in ask_prices:
            if price > order.price:  # no more matching prices
                break

            while order.size > 0 and price in self.asks and self.asks[price]:
                maker = self.asks[price][0]
                match_size = min(order.size, maker.size)

                # fill
                fill = Fill(
                    taker_order_id=order.order_id,
                    maker_order_id=maker.order_id,
                    price=price,
                    size=match_size,
                    timestamp=int(time.time() * 1000),
                )
                fills.append(fill)

                # update sizes
                order.size -= match_size
                maker.size -= match_size

                # remove filled maker order
                if maker.size == 0:
                    self.asks[price].pop(0)
                    del self.order_map[maker.order_id]
                    if not self.asks[price]:
                        del self.asks[price]

        return fills

    def _match_sell(self, order: Order) -> List[Fill]:
        """match a sell order against the bid side"""
        fills = []
        bid_prices = sorted(self.bids.keys(), reverse=True)

        for price in bid_prices:
            if price < order.price:  # no more matching prices
                break

            while order.size > 0 and price in self.bids and self.bids[price]:
                maker = self.bids[price][0]
                match_size = min(order.size, maker.size)

                # fill
                fill = Fill(
                    taker_order_id=order.order_id,
                    maker_order_id=maker.order_id,
                    price=price,
                    size=match_size,
                    timestamp=int(time.time() * 1000),
                )
                fills.append(fill)

                # update sizes
                order.size -= match_size
                maker.size -= match_size

                # remove filled maker order
                if maker.size == 0:
                    self.bids[price].pop(0)
                    del self.order_map[maker.order_id]
                    if not self.bids[price]:
                        del self.bids[price]

        return fills

    def _add_to_book(self, order: Order) -> None:
        """add remaining order to the book"""
        book = self.bids if order.side == "buy" else self.asks
        if order.price not in book:
            book[order.price] = []
        book[order.price].append(order)
        self.order_map[order.order_id] = (order.side, order.price)

    def get_snapshot(self):
        """
        Returns the current bids and asks as lists of [price, quantity] string pairs.
        Bids are sorted descending, asks ascending.
        """
        bids = []
        for price in sorted(self.bids.keys(), reverse=True):
            total_qty = sum(order.size for order in self.bids[price])
            bids.append([str(price), str(total_qty)])
        asks = []
        for price in sorted(self.asks.keys()):
            total_qty = sum(order.size for order in self.asks[price])
            asks.append([str(price), str(total_qty)])
        return bids, asks

    def get_best_bid(self) -> Optional[Decimal]:
        """return the highest bid price or None if no bids"""
        if not self.bids:
            return None
        return max(self.bids.keys())

    def get_best_ask(self) -> Optional[Decimal]:
        """return the lowest ask price or None if no asks"""
        if not self.asks:
            return None
        return min(self.asks.keys())
