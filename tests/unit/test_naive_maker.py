"""
unit tests for naive market making strategy
"""

from decimal import Decimal

from strategy.naive_maker import NaiveMaker, NaiveMakerConfig


def test_quote_prices_zero_spread():
    """test quoting with zero spread"""
    mid_price = Decimal("100.0")
    best_bid = Decimal("99.0")
    best_ask = Decimal("101.0")
    config = NaiveMakerConfig(spread=Decimal("0.0"))
    maker = NaiveMaker(config)
    bid_quote, ask_quote = maker.quote_prices(
        mid_price=mid_price,
        best_bid=best_bid,
        best_ask=best_ask,
    )
    assert bid_quote.price == mid_price
    assert ask_quote.price == mid_price
    assert bid_quote.size > 0
    assert ask_quote.size > 0


def test_quote_prices_positive_spread():
    """test quoting with positive spread"""
    mid_price = Decimal("100.0")
    best_bid = Decimal("99.0")
    best_ask = Decimal("101.0")
    config = NaiveMakerConfig(spread=Decimal("1.0"))
    maker = NaiveMaker(config)
    bid_quote, ask_quote = maker.quote_prices(
        mid_price=mid_price,
        best_bid=best_bid,
        best_ask=best_ask,
    )
    assert bid_quote.price < mid_price
    assert ask_quote.price > mid_price
    assert bid_quote.size > 0
    assert ask_quote.size > 0


def test_quote_prices_negative_mid():
    """test quoting with negative mid price"""
    mid_price = Decimal("-100.0")
    best_bid = Decimal("-101.0")
    best_ask = Decimal("-99.0")
    config = NaiveMakerConfig(spread=Decimal("1.0"))
    maker = NaiveMaker(config)
    bid_quote, ask_quote = maker.quote_prices(
        mid_price=mid_price,
        best_bid=best_bid,
        best_ask=best_ask,
    )
    assert bid_quote.price < mid_price
    assert ask_quote.price > mid_price
    assert bid_quote.size > 0
    assert ask_quote.size > 0


def test_quote_prices_no_market():
    """test quoting without market quotes"""
    mid_price = Decimal("100.0")
    config = NaiveMakerConfig(spread=Decimal("1.0"))
    maker = NaiveMaker(config)
    bid_quote, ask_quote = maker.quote_prices(
        mid_price=mid_price,
        best_bid=None,
        best_ask=None,
    )
    assert bid_quote.price < mid_price
    assert ask_quote.price > mid_price
    assert bid_quote.size > 0
    assert ask_quote.size > 0
    assert ask_quote.price - bid_quote.price == Decimal("1.0")
