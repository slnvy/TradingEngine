from match_engine import MatchEngine, Side


def test_basic_matching():
    engine = MatchEngine()
    # Insert a buy order
    fills = engine.insert("buy1", Side.BUY, 100.0, 1.0, 1)
    assert len(fills) == 0  # No matches yet
    # Insert a matching sell order
    fills = engine.insert("sell1", Side.SELL, 100.0, 1.0, 2)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.taker_order_id == "sell1"
    assert fill.maker_order_id == "buy1"
    assert fill.price == 100.0
    assert fill.size == 1.0
    assert fill.timestamp == 2


def test_partial_fills():
    engine = MatchEngine()
    # Insert a large buy order
    fills = engine.insert("buy1", Side.BUY, 100.0, 2.0, 1)
    assert len(fills) == 0
    # Insert a smaller sell order
    fills = engine.insert("sell1", Side.SELL, 100.0, 1.0, 2)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.size == 1.0
    # Insert another sell order
    fills = engine.insert("sell2", Side.SELL, 100.0, 1.0, 3)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.size == 1.0


def test_price_priority():
    engine = MatchEngine()
    # Insert multiple buy orders at different prices
    engine.insert("buy1", Side.BUY, 100.0, 1.0, 1)
    engine.insert("buy2", Side.BUY, 101.0, 1.0, 2)
    engine.insert("buy3", Side.BUY, 99.0, 1.0, 3)
    # Insert a sell order that should match with the highest bid
    fills = engine.insert("sell1", Side.SELL, 100.0, 1.0, 4)
    assert len(fills) == 1
    assert fills[0].maker_order_id == "buy2"  # Should match with highest bid
    assert fills[0].price == 101.0


def test_cancel_order():
    engine = MatchEngine()
    # Insert an order
    engine.insert("order1", Side.BUY, 100.0, 1.0, 1)
    # Cancel it
    assert engine.cancel("order1") is True
    # Try to cancel again
    assert engine.cancel("order1") is False
    # Try to match against cancelled order
    fills = engine.insert("sell1", Side.SELL, 100.0, 1.0, 2)
    assert len(fills) == 0


def test_multiple_fills():
    engine = MatchEngine()
    # Insert multiple buy orders at the same price
    engine.insert("buy1", Side.BUY, 100.0, 1.0, 1)
    engine.insert("buy2", Side.BUY, 100.0, 1.0, 2)
    engine.insert("buy3", Side.BUY, 100.0, 1.0, 3)
    # Insert a large sell order that should match with all buys
    fills = engine.insert("sell1", Side.SELL, 100.0, 2.5, 4)
    assert len(fills) == 3
    assert sum(fill.size for fill in fills) == 2.5
