"""
unit tests for microprice feature calculation
"""

from decimal import Decimal

import pytest

from features.micro_price import calculate_microprice


def test_microprice_equal_volumes():
    """test microprice calculation with equal bid and ask volumes"""
    bids = [(Decimal("100.0"), Decimal("1.0"))]
    asks = [(Decimal("101.0"), Decimal("1.0"))]
    microprice = calculate_microprice(bids, asks)
    assert microprice == Decimal("100.5")


def test_microprice_empty_book():
    """test microprice calculation with empty order book"""
    bids = []
    asks = []
    microprice = calculate_microprice(bids, asks)
    assert microprice == Decimal("0.0")


def test_microprice_zero_volume():
    """test microprice calculation with zero volumes"""
    bids = [(Decimal("100.0"), Decimal("0.0"))]
    asks = [(Decimal("101.0"), Decimal("0.0"))]
    microprice = calculate_microprice(bids, asks)
    assert microprice == Decimal("100.5")


def test_microprice_unequal_volumes():
    """test microprice calculation with unequal bid and ask volumes"""
    bids = [(Decimal("100.0"), Decimal("2.0"))]
    asks = [(Decimal("101.0"), Decimal("1.0"))]
    microprice = calculate_microprice(bids, asks)
    assert float(microprice) == pytest.approx(100.6666666667, abs=1e-6)
