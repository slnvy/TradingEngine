"""
microprice feature calculation
"""

from decimal import Decimal
from typing import List, Tuple


def calculate_microprice(
    bids: List[Tuple[Decimal, Decimal]], asks: List[Tuple[Decimal, Decimal]]
) -> Decimal:
    """
    calculate microprice as weighted average of best bid and ask prices

    args:
        bids: list of (price, volume) tuples for bids
        asks: list of (price, volume) tuples for asks

    returns:
        microprice as a decimal
    """
    if not bids or not asks:
        return Decimal("0.0")

    best_bid_price, best_bid_volume = bids[0]
    best_ask_price, best_ask_volume = asks[0]

    total_volume = best_bid_volume + best_ask_volume
    if total_volume == 0:
        return (best_bid_price + best_ask_price) / Decimal("2.0")

    microprice = (
        best_bid_price * best_ask_volume + best_ask_price * best_bid_volume
    ) / total_volume
    return microprice
