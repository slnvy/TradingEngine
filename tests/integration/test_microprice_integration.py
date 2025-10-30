"""
integration tests for microprice feature
"""

from decimal import Decimal

from features.micro_price import calculate_microprice
from lob.order_book import Order, OrderBook


def normalize_decimal(d: Decimal, places: int = 8) -> Decimal:
    """normalize decimal precision for consistent comparisons"""
    return Decimal(str(d)).quantize(Decimal(10) ** -places)


def test_microprice_with_order_book():
    """test microprice calculation with live order book updates"""
    # initialize order book
    order_book = OrderBook()

    # add some orders
    orders = [
        Order(
            "1", "buy", Decimal("50000.00"), Decimal("2.0"), 1000
        ),  # 2 btc bid at 50k
        Order(
            "2", "buy", Decimal("49900.00"), Decimal("1.0"), 1001
        ),  # 1 btc bid at 49.9k
        Order(
            "3", "sell", Decimal("50100.00"), Decimal("1.5"), 1002
        ),  # 1.5 btc ask at 50.1k
        Order(
            "4", "sell", Decimal("50200.00"), Decimal("1.0"), 1003
        ),  # 1 btc ask at 50.2k
    ]

    for order in orders:
        order_book.insert(order)

    # get best bid and ask with volumes
    best_bid = max(order_book.bids.keys())
    best_ask = min(order_book.asks.keys())
    bid_volume = sum(order.size for order in order_book.bids[best_bid])
    ask_volume = sum(order.size for order in order_book.asks[best_ask])

    # calculate microprice
    bids = [(best_bid, bid_volume)]
    asks = [(best_ask, ask_volume)]
    microprice = calculate_microprice(bids, asks)

    # expected microprice calculation
    # (50000 * 1.5 + 50100 * 2.0) / (1.5 + 2.0) = 50057.14285714
    expected = Decimal("50057.14285714")
    assert normalize_decimal(microprice) == normalize_decimal(expected)


def test_microprice_with_market_impact():
    """test microprice behavior with significant volume imbalance"""
    # initialize order book
    order_book = OrderBook()

    # add orders with large volume imbalance
    orders = [
        Order("1", "buy", Decimal("50000.00"), Decimal("10.0"), 1000),  # 10 btc bid
        Order("2", "sell", Decimal("50100.00"), Decimal("1.0"), 1001),  # 1 btc ask
    ]

    for order in orders:
        order_book.insert(order)

    # get best bid and ask with volumes
    best_bid = max(order_book.bids.keys())
    best_ask = min(order_book.asks.keys())
    bid_volume = sum(order.size for order in order_book.bids[best_bid])
    ask_volume = sum(order.size for order in order_book.asks[best_ask])

    # calculate microprice
    bids = [(best_bid, bid_volume)]
    asks = [(best_ask, ask_volume)]
    microprice = calculate_microprice(bids, asks)

    # with 10:1 volume ratio microprice should be closer to bid
    # (50000 * 1 + 50100 * 10) / (1 + 10) = 50090.90909091
    expected = Decimal("50090.90909091")
    assert normalize_decimal(microprice) == normalize_decimal(expected)


def test_microprice_after_trades():
    """test microprice updates after trades affect the book"""
    order_book = OrderBook()

    # initial state
    orders = [
        Order("1", "buy", Decimal("50000.00"), Decimal("2.0"), 1000),
        Order("2", "sell", Decimal("50100.00"), Decimal("2.0"), 1001),
    ]

    for order in orders:
        order_book.insert(order)

    # execute a trade that takes half the ask liquidity
    taker = Order("3", "buy", Decimal("50100.00"), Decimal("1.0"), 1002)
    order_book.insert(taker)

    # get updated best levels
    best_bid = max(order_book.bids.keys())
    best_ask = min(order_book.asks.keys())
    bid_volume = sum(order.size for order in order_book.bids[best_bid])
    ask_volume = sum(order.size for order in order_book.asks[best_ask])

    # calculate microprice after trade
    bids = [(best_bid, bid_volume)]
    asks = [(best_ask, ask_volume)]
    microprice = calculate_microprice(bids, asks)

    # after trade 2.0 on bid 1.0 on ask
    # (50000 * 1 + 50100 * 2) / (1 + 2) = 50066.66666667
    expected = Decimal("50066.66666667")
    assert normalize_decimal(microprice) == normalize_decimal(expected)
