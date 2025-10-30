"""
Order book imbalance feature calculation
"""

from decimal import Decimal
from typing import List


def calculate_imbalance(
    bids: List[List[str]], asks: List[List[str]], levels: int = 1
) -> float:
    """
    Calculate order book imbalance at specified number of levels

    Imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume)

    Args:
        bids: list of [price, quantity] pairs, sorted descending
        asks: list of [price, quantity] pairs, sorted ascending
        levels: number of levels to consider (default: 1)

    Returns:
        float between -1 and 1, where:
        -1 means all volume is on ask side
        0 means equal volume on both sides
        1 means all volume is on bid side
    """
    # Convert string quantities to decimal
    bid_volume = sum(Decimal(qty) for _, qty in bids[:levels])
    ask_volume = sum(Decimal(qty) for _, qty in asks[:levels])

    total_volume = bid_volume + ask_volume
    if total_volume == 0:
        return 0.0

    return float((bid_volume - ask_volume) / total_volume)


def get_imbalance_features(bids: List[List[str]], asks: List[List[str]]) -> dict:
    """
    Calculate imbalance features at multiple levels

    Args:
        bids: list of [price, quantity] pairs, sorted descending
        asks: list of [price, quantity] pairs, sorted ascending

    Returns:
        dict with imbalance values at different levels
    """
    return {
        "imbalance_1": calculate_imbalance(bids, asks, levels=1),
        "imbalance_2": calculate_imbalance(bids, asks, levels=2),
        "imbalance_5": calculate_imbalance(bids, asks, levels=5),
    }
