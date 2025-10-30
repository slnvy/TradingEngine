import pytest

from models.inventory_skew import InventorySkew, InventorySkewConfig


@pytest.fixture
def default_config():
    return InventorySkewConfig(
        max_position=1.0,
        skew_factor=0.5,
        min_spread_bps=1.0,
        spread_factor=1.0,
        continuity_clip=0.1,
    )


@pytest.fixture
def skew(default_config):
    return InventorySkew(default_config)


def test_basic_skew_behavior(skew):
    """test that quotes are skewed in the correct direction based on inventory"""
    mid_price = 100.0

    # neutral inventory
    bid, ask = skew.apply_skew(mid_price, 0.0)
    assert bid < mid_price < ask
    assert abs(bid - mid_price) == abs(ask - mid_price)  # symmetric around mid

    # positive inventory -> encourage selling
    bid_pos, ask_pos = skew.apply_skew(mid_price, 0.5)
    assert bid_pos < bid  # lower bid
    # with positive inventory, we want to encourage selling
    # spread wider and centered lower
    assert ask_pos - bid_pos > ask - bid  # wider spread
    assert (bid_pos + ask_pos) / 2 < (bid + ask) / 2  # center shifted down

    # negative inventory -> encourage buying
    bid_neg, ask_neg = skew.apply_skew(mid_price, -0.5)
    assert bid_neg > bid  # higher bid
    # negative inventory means we want to encourage buying
    # spread wider and centered higher
    assert ask_neg - bid_neg > ask - bid  # wider spread
    assert (bid_neg + ask_neg) / 2 > (bid + ask) / 2  # center shifted up


def test_spread_widening(skew):
    """test that spread increases with inventory magnitude"""
    mid_price = 100.0

    # get baseline spread at zero inventory
    bid0, ask0 = skew.apply_skew(mid_price, 0.0)
    base_spread = ask0 - bid0

    # spread widens with increasing inventory
    for inv in [0.25, 0.5, 0.75, 1.0]:
        bid, ask = skew.apply_skew(mid_price, inv)
        spread = ask - bid
        assert spread > base_spread
        assert spread > base_spread * (
            1 + inv * skew.config.spread_factor * 0.9
        )  # 0.9 to account for floating point


def test_minimum_spread(skew):
    """test that minimum spread is maintained even at max inventory"""
    mid_price = 100.0
    min_spread = mid_price * skew.config.min_spread_bps / 10_000.0

    # at max inventory
    bid, ask = skew.apply_skew(mid_price, skew.config.max_position)
    assert ask - bid >= min_spread

    # at min inventory
    bid, ask = skew.apply_skew(mid_price, -skew.config.max_position)
    assert ask - bid >= min_spread


def test_inventory_normalization(skew):
    """test that inventory is properly normalized to [-1, 1]"""
    mid_price = 100.0

    # test values beyond max_position
    bid1, ask1 = skew.apply_skew(mid_price, 2.0)  # clipped to 1.0
    bid2, ask2 = skew.apply_skew(mid_price, 1.0)  # same as above
    assert bid1 == bid2
    assert ask1 == ask2

    # test values below -max_position
    bid3, ask3 = skew.apply_skew(mid_price, -2.0)  # clipped to -1.0
    bid4, ask4 = skew.apply_skew(mid_price, -1.0)  # same as above
    assert bid3 == bid4
    assert ask3 == ask4


def test_continuity_protection(skew):
    """test that price changes are limited by continuity_clip"""
    mid_price = 100.0

    # first call establishes baseline
    bid1, ask1 = skew.apply_skew(mid_price, 0.0)

    # second call with same parameters should be identical
    bid2, ask2 = skew.apply_skew(mid_price, 0.0)
    assert bid1 == bid2
    assert ask1 == ask2

    # third call with large inventory change
    bid3, ask3 = skew.apply_skew(mid_price, 1.0)
    assert abs(bid3 - bid2) <= skew.config.continuity_clip
    assert abs(ask3 - ask2) <= skew.config.continuity_clip


def test_config_validation():
    """test that config parameters are properly validated"""
    # test invalid max_position
    with pytest.raises(ValueError):
        InventorySkewConfig(max_position=0.0)

    # test invalid skew_factor
    with pytest.raises(ValueError):
        InventorySkewConfig(skew_factor=-0.1)

    # test invalid min_spread_bps
    with pytest.raises(ValueError):
        InventorySkewConfig(min_spread_bps=0.0)

    # test invalid spread_factor
    with pytest.raises(ValueError):
        InventorySkewConfig(spread_factor=-0.1)

    # test invalid continuity_clip
    with pytest.raises(ValueError):
        InventorySkewConfig(continuity_clip=0.0)


def test_skew_spread_interaction():
    """test that skew and spread factors interact correctly"""
    # create two configs with different skew/spread ratios
    config1 = InventorySkewConfig(
        max_position=1.0,
        skew_factor=0.5,  # moderate skew
        spread_factor=1.0,  # moderate spread
        min_spread_bps=1.0,
        continuity_clip=0.1,
    )

    config2 = InventorySkewConfig(
        max_position=1.0,
        skew_factor=1.0,  # aggressive skew
        spread_factor=0.5,  # conservative spread
        min_spread_bps=1.0,
        continuity_clip=0.1,
    )

    skew1 = InventorySkew(config1)
    skew2 = InventorySkew(config2)

    mid_price = 100.0
    inventory = 0.5  # positive inventory

    # get quotes from both configs
    bid1, ask1 = skew1.apply_skew(mid_price, inventory)
    bid2, ask2 = skew2.apply_skew(mid_price, inventory)

    # config2 has more aggressive skew, center shifts more
    center1 = (bid1 + ask1) / 2
    center2 = (bid2 + ask2) / 2
    assert abs(center2 - mid_price) > abs(center1 - mid_price)

    # config1 has more aggressive spread, wider spread
    spread1 = ask1 - bid1
    spread2 = ask2 - bid2
    assert spread1 > spread2

    # both maintain minimum spread
    min_spread = mid_price * config1.min_spread_bps / 10_000.0
    assert spread1 >= min_spread
    assert spread2 >= min_spread
