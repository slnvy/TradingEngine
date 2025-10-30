"""
unit tests for order book implementation
"""

from decimal import Decimal

import pytest

from lob.order_book import Order, OrderBook


@pytest.fixture
def order_book():
    """fixture for a fresh order book"""
    return OrderBook()


def test_order_book_initialization(order_book):
    """test order book initialization"""
    assert order_book.bids == {}
    assert order_book.asks == {}
    assert order_book.order_map == {}


def test_insert_buy_order(order_book):
    """test inserting a buy order"""
    order = Order(
        order_id="1",
        side="buy",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567890,
    )
    fills = order_book.insert(order)
    assert len(fills) == 0
    assert order.price in order_book.bids
    assert len(order_book.bids[order.price]) == 1
    assert order_book.order_map[order.order_id] == ("buy", order.price)


def test_insert_sell_order(order_book):
    """test inserting a sell order"""
    order = Order(
        order_id="1",
        side="sell",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567890,
    )
    fills = order_book.insert(order)
    assert len(fills) == 0
    assert order.price in order_book.asks
    assert len(order_book.asks[order.price]) == 1
    assert order_book.order_map[order.order_id] == ("sell", order.price)


def test_match_buy_order(order_book):
    """test matching a buy order against existing asks"""
    # first insert a sell order
    sell_order = Order(
        order_id="1",
        side="sell",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567890,
    )
    order_book.insert(sell_order)
    # then insert a matching buy order
    buy_order = Order(
        order_id="2",
        side="buy",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567891,
    )
    fills = order_book.insert(buy_order)
    assert len(fills) == 1
    assert fills[0].taker_order_id == "2"
    assert fills[0].maker_order_id == "1"
    assert fills[0].price == Decimal("50000.00")
    assert fills[0].size == Decimal("1.0")
    assert sell_order.price not in order_book.asks  # sell order should be removed


def test_match_sell_order(order_book):
    """test matching a sell order against existing bids"""
    # first insert a buy order
    buy_order = Order(
        order_id="1",
        side="buy",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567890,
    )
    order_book.insert(buy_order)
    # then insert a matching sell order
    sell_order = Order(
        order_id="2",
        side="sell",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567891,
    )
    fills = order_book.insert(sell_order)
    assert len(fills) == 1
    assert fills[0].taker_order_id == "2"
    assert fills[0].maker_order_id == "1"
    assert fills[0].price == Decimal("50000.00")
    assert fills[0].size == Decimal("1.0")
    assert buy_order.price not in order_book.bids  # buy order should be removed


def test_cancel_order(order_book):
    """test cancelling an existing order"""
    order = Order(
        order_id="1",
        side="buy",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567890,
    )
    order_book.insert(order)
    cancelled = order_book.cancel("1")
    assert cancelled == order
    assert order.price not in order_book.bids
    assert "1" not in order_book.order_map


def test_cancel_nonexistent_order(order_book):
    """test cancelling a non-existent order"""
    cancelled = order_book.cancel("1")
    assert cancelled is None


def test_partial_fill(order_book):
    """test partial fill of an order"""
    # insert a sell order
    sell_order = Order(
        order_id="1",
        side="sell",
        price=Decimal("50000.00"),
        size=Decimal("2.0"),
        timestamp=1234567890,
    )
    order_book.insert(sell_order)
    # insert a buy order for half the size
    buy_order = Order(
        order_id="2",
        side="buy",
        price=Decimal("50000.00"),
        size=Decimal("1.0"),
        timestamp=1234567891,
    )
    fills = order_book.insert(buy_order)
    assert len(fills) == 1
    assert fills[0].size == Decimal("1.0")
    assert sell_order.size == Decimal("1.0")  # remaining size
    assert sell_order.price in order_book.asks  # sell order should still exist
