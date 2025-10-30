"""
data schemas for binance websocket messages
"""

from dataclasses import dataclass
from typing import List


@dataclass
class DepthUpdate:
    """schema for depth update messages from binance websocket"""

    e: str  # event type
    E: int  # event time
    s: str  # symbol
    U: int  # first update id in event
    u: int  # final update id in event
    b: List[List[str]]  # bids to be updated [price quantity]
    a: List[List[str]]  # asks to be updated [price quantity]
