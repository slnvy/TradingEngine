"""
short-term volatility feature calculation
"""

from collections import deque
from decimal import Decimal
from typing import Optional


class VolatilityCalculator:
    """calculates rolling window volatility of mid price"""

    def __init__(self, window_size: int = 100):
        """
        initialize volatility calculator

        args:
            window_size: number of mid prices to keep in rolling window
        """
        self.window_size = window_size
        self.prices = deque(maxlen=window_size)
        self._last_volatility: Optional[float] = None

    def update(self, mid_price: Decimal) -> float:
        """
        update volatility calculation with new mid price

        args:
            mid_price: current mid price

        returns:
            current volatility estimate
        """
        self.prices.append(float(mid_price))

        if len(self.prices) < 2:
            self._last_volatility = 0.0
            return self._last_volatility

        # calculate returns
        returns = []
        for i in range(1, len(self.prices)):
            ret = (self.prices[i] - self.prices[i - 1]) / self.prices[i - 1]
            returns.append(ret)

        if len(returns) < 2:
            self._last_volatility = 0.0
            return self._last_volatility

        # calculate volatility as standard deviation of returns
        mean_return = sum(returns) / len(returns)
        squared_diff_sum = sum((r - mean_return) ** 2 for r in returns)
        variance = squared_diff_sum / (len(returns) - 1)
        self._last_volatility = (variance**0.5) * (252**0.5)  # annualized

        return self._last_volatility

    @property
    def volatility(self) -> float:
        """get current volatility estimate"""
        return self._last_volatility if self._last_volatility is not None else 0.0
