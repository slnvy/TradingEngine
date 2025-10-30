"""
unit tests for order book imbalance feature calculation
"""

import pytest

from features.imbalance import calculate_imbalance, get_imbalance_features


def test_calculate_imbalance_equal_volume():
    """test imbalance calculation with equal volume on both sides"""
    bids = [["100", "1.0"], ["99", "1.0"]]
    asks = [["101", "1.0"], ["102", "1.0"]]

    assert calculate_imbalance(bids, asks, levels=1) == 0.0
    assert calculate_imbalance(bids, asks, levels=2) == 0.0


def test_calculate_imbalance_bid_heavy():
    """test imbalance calculation with more volume on bid side"""
    bids = [["100", "2.0"], ["99", "1.0"]]
    asks = [["101", "1.0"], ["102", "1.0"]]

    assert calculate_imbalance(bids, asks, levels=1) == pytest.approx(
        0.3333333333333333
    )  # (2-1)/(2+1)
    assert calculate_imbalance(bids, asks, levels=2) == pytest.approx(
        0.2
    )  # (3-2)/(3+2)


def test_calculate_imbalance_ask_heavy():
    """test imbalance calculation with more volume on ask side"""
    bids = [["100", "1.0"], ["99", "1.0"]]
    asks = [["101", "2.0"], ["102", "1.0"]]

    assert calculate_imbalance(bids, asks, levels=1) == pytest.approx(
        -0.3333333333333333
    )  # (1-2)/(1+2)
    assert calculate_imbalance(bids, asks, levels=2) == pytest.approx(
        -0.2
    )  # (2-3)/(2+3)


def test_calculate_imbalance_empty_book():
    """test imbalance calculation with empty order book"""
    bids = []
    asks = []

    assert calculate_imbalance(bids, asks) == 0.0


def test_get_imbalance_features():
    """test getting imbalance features at multiple levels"""
    bids = [["100", "2.0"], ["99", "1.0"], ["98", "1.0"]]
    asks = [["101", "1.0"], ["102", "1.0"], ["103", "1.0"]]

    features = get_imbalance_features(bids, asks)

    assert "imbalance_1" in features
    assert "imbalance_2" in features
    assert "imbalance_5" in features

    assert features["imbalance_1"] == pytest.approx(0.3333333333333333)  # (2-1)/(2+1)
    assert features["imbalance_2"] == pytest.approx(0.2)  # (3-2)/(3+2)
    assert features["imbalance_5"] == pytest.approx(0.14285714285714285)  # (4-3)/(4+3)
