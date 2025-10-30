from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class InventorySkewConfig:
    # maximum allowed inventory position in base currency
    max_position: float = 1.0
    # how aggressively to skew quotes based on inventory
    skew_factor: float = 0.5
    # minimum spread to maintain even at max inventory
    min_spread_bps: float = 1.0
    # optional widening as inventory grows
    spread_factor: float = 1.0
    # max price change per side between calls
    continuity_clip: float = 0.1
    # tolerance for floating point comparisons
    float_tolerance: float = 1e-10

    def __post_init__(self):
        """validate config parameters"""
        if self.max_position <= 0:
            raise ValueError("max_position must be positive")
        if self.skew_factor <= 0:
            raise ValueError("skew_factor must be positive")
        if self.min_spread_bps <= 0:
            raise ValueError("min_spread_bps must be positive")
        if self.spread_factor <= 0:
            raise ValueError("spread_factor must be positive")
        if self.continuity_clip <= 0:
            raise ValueError("continuity_clip must be positive")
        if self.float_tolerance <= 0:
            raise ValueError("float_tolerance must be positive")


class InventorySkew:
    """computes quote adjustments based on current inventory position

    the skew logic follows a risk management approach where:
    - positive inventory: lower bid, raise ask to encourage selling
    - negative inventory: raise bid, lower ask to encourage buying
    - skew and spread increase as inventory moves away from 0
    """

    def __init__(self, config: InventorySkewConfig):
        self.config = config
        self._prev_bid = None
        self._prev_ask = None

    def apply_skew(self, mid_price: float, inventory: float) -> Tuple[float, float]:
        """apply inventory-based skew to mid price to get bid/ask prices

        args:
            mid_price: current mid price
            inventory: current inventory level

        returns:
            tuple of (bid_price, ask_price)
        """
        # normalize inventory to [-1, 1] so we never explode the quotes
        inv = np.clip(inventory / self.config.max_position, -1.0, 1.0)

        # spread calculation (monotonic increase with |inv|, never < min_spread)
        min_spread = mid_price * self.config.min_spread_bps / 10_000.0
        # abs value for monotonic increase in both directions
        abs_inv = abs(inv)
        # spread increases with inventory magnitude
        spread = min_spread * (1.0 + abs_inv * self.config.spread_factor)
        half_spread = spread / 2.0

        # centre-shift (skew) - directional and inventory-proportional
        # long (+inv): shift centre down -> bid down, ask up
        # short (-inv): shift centre up -> bid up, ask down
        # raw inventory for directional skew
        centre_shift = -inv * self.config.skew_factor * spread

        # raw bid/ask around shifted centre (ask > bid always)
        # spread maintained by applying half_spread symmetrically
        bid_price = mid_price + centre_shift - half_spread
        ask_price = mid_price + centre_shift + half_spread

        # continuity guard (max move per side per call)
        if self._prev_bid is not None:
            lim = self.config.continuity_clip
            bid_move = bid_price - self._prev_bid
            ask_move = ask_price - self._prev_ask

            # handle floating point precision
            if abs(abs(bid_move) - lim) < self.config.float_tolerance:
                bid_move = np.sign(bid_move) * lim
            if abs(abs(ask_move) - lim) < self.config.float_tolerance:
                ask_move = np.sign(ask_move) * lim

            bid_price = self._prev_bid + np.clip(bid_move, -lim, lim)
            ask_price = self._prev_ask + np.clip(ask_move, -lim, lim)

        self._prev_bid, self._prev_ask = bid_price, ask_price

        return bid_price, ask_price
