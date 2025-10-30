"""
Order book implementation for maintaining limit order book state
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


@dataclass
class Order:
    """Represents a single order in the book"""

    order_id: str
    side: str  # 'buy' or 'sell'
    price: Decimal
    size: Decimal
    timestamp: int


@dataclass
class Fill:
    """Represents a fill event from matching orders"""

    taker_order_id: str
    maker_order_id: str
    price: Decimal
    size: Decimal
    timestamp: int


class OrderBook:
    """Maintains the current state of the limit order book"""

    def __init__(self):
        # price level -> list of orders at that price
        self.bids: Dict[Decimal, List[Order]] = {}
        self.asks: Dict[Decimal, List[Order]] = {}
        # order_id -> (side, price) for quick lookup
        self.order_map: Dict[str, Tuple[str, Decimal]] = {}

    def insert(self, order: Order) -> List[Fill]:
        """
        Insert a new order into the book

        Returns list of fills if the order was matched
        """
        if order.side not in ["buy", "sell"]:
            raise ValueError(f"Invalid order side: {order.side}")

        fills = []

        # Try to match the order
        if order.side == "buy":
            fills = self._match_buy(order)
        else:
            fills = self._match_sell(order)

        # If order still has size, add to book
        if order.size > 0:
            self._add_to_book(order)

        return fills

    def cancel(self, order_id: str) -> Optional[Order]:
        """
        Cancel an existing order

        Returns the cancelled order if found, None otherwise
        """
        if order_id not in self.order_map:
            return None

        side, price = self.order_map[order_id]
        book = self.bids if side == "buy" else self.asks

        # Find and remove the order
        if price in book:
            for i, order in enumerate(book[price]):
                if order.order_id == order_id:
                    cancelled = book[price].pop(i)
                    if not book[price]:  # Remove empty price level
                        del book[price]
                    del self.order_map[order_id]
                    return cancelled

        return None

    def _match_buy(self, order: Order) -> List[Fill]:
        """Match a buy order against the ask side"""
        fills = []
        ask_prices = sorted(self.asks.keys())

        for price in ask_prices:
            if price > order.price:  # No more matching prices
                break

            while order.size > 0 and price in self.asks and self.asks[price]:
                maker = self.asks[price][0]
                match_size = min(order.size, maker.size)

                # Create fill
                fill = Fill(
                    taker_order_id=order.order_id,
                    maker_order_id=maker.order_id,
                    price=price,
                    size=match_size,
                    timestamp=order.timestamp,
                )
                fills.append(fill)

                # Update sizes
                order.size -= match_size
                maker.size -= match_size

                # Remove filled maker order
                if maker.size == 0:
                    self.asks[price].pop(0)
                    del self.order_map[maker.order_id]
                    if not self.asks[price]:
                        del self.asks[price]

        return fills

    def _match_sell(self, order: Order) -> List[Fill]:
        """Match a sell order against the bid side"""
        fills = []
        bid_prices = sorted(self.bids.keys(), reverse=True)

        for price in bid_prices:
            if price < order.price:  # No more matching prices
                break

            while order.size > 0 and price in self.bids and self.bids[price]:
                maker = self.bids[price][0]
                match_size = min(order.size, maker.size)

                # Create fill
                fill = Fill(
                    taker_order_id=order.order_id,
                    maker_order_id=maker.order_id,
                    price=price,
                    size=match_size,
                    timestamp=order.timestamp,
                )
                fills.append(fill)

                # Update sizes
                order.size -= match_size
                maker.size -= match_size

                # Remove filled maker order
                if maker.size == 0:
                    self.bids[price].pop(0)
                    del self.order_map[maker.order_id]
                    if not self.bids[price]:
                        del self.bids[price]

        return fills

    def _add_to_book(self, order: Order) -> None:
        """Add remaining order to the book"""
        book = self.bids if order.side == "buy" else self.asks
        if order.price not in book:
            book[order.price] = []
        book[order.price].append(order)
        self.order_map[order.order_id] = (order.side, order.price)

    def get_snapshot(self) -> Tuple[List[List[str]], List[List[str]]]:
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
