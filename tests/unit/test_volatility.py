"""
unit tests for short-term volatility feature calculation
"""

from decimal import Decimal

import pytest

from features.volatility import VolatilityCalculator


def test_volatility_calculator_initialization():
    """test volatility calculator initialization"""
    calc = VolatilityCalculator(window_size=100)
    assert calc.window_size == 100
    assert calc.volatility == 0.0


def test_volatility_calculator_single_price():
    """test volatility calculation with single price"""
    calc = VolatilityCalculator(window_size=100)
    assert calc.update(Decimal("100.0")) == 0.0
    assert calc.volatility == 0.0


def test_volatility_calculator_constant_price():
    """test volatility calculation with constant price"""
    calc = VolatilityCalculator(window_size=100)
    for _ in range(10):
        assert calc.update(Decimal("100.0")) == 0.0
    assert calc.volatility == 0.0


def test_volatility_calculator_linear_price():
    """test volatility calculation with linear price movement"""
    calc = VolatilityCalculator(window_size=100)
    prices = [Decimal(str(100 + i)) for i in range(10)]

    for price in prices:
        calc.update(price)

    # with linear price movement, returns are constant
    # volatility should be very close to 0 (allow small tolerance)
    assert calc.volatility == pytest.approx(0.0, abs=1e-2)


def test_volatility_calculator_alternating_price():
    """test volatility calculation with alternating price"""
    calc = VolatilityCalculator(window_size=100)
    prices = [Decimal("100.0"), Decimal("101.0")] * 5

    for price in prices:
        calc.update(price)

    # with alternating price, volatility should be non-zero
    assert calc.volatility > 0.0


def test_volatility_calculator_window_size():
    """test volatility calculation respects window size"""
    calc = VolatilityCalculator(window_size=3)

    # add prices that would give high volatility
    calc.update(Decimal("100.0"))
    calc.update(Decimal("101.0"))
    calc.update(Decimal("102.0"))
    high_vol = calc.volatility

    # add more prices that would give low volatility
    calc.update(Decimal("102.0"))
    calc.update(Decimal("102.0"))
    calc.update(Decimal("102.0"))

    # volatility should be lower now due to window size
    assert calc.volatility < high_vol
