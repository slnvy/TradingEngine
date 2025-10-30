"""naive market making strategy with dynamic spread and size"""

from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple, Tuple


class Quote(NamedTuple):
    price: Decimal
    size: Decimal


@dataclass
class NaiveMakerConfig:
    spread: Decimal = Decimal("0.001")
    aggressiveness: Decimal = Decimal("0.2")
    base_size: Decimal = Decimal("0.001")


class NaiveMaker:
    def __init__(self, config: NaiveMakerConfig):
        self.config = config

    def quote_prices(
        self,
        mid_price: Decimal,
        volatility: Decimal = None,
        bid_probability: Decimal = None,
        ask_probability: Decimal = None,
        inventory: Decimal = Decimal("0"),
        best_bid: Decimal = None,
        best_ask: Decimal = None,
        bids: list = None,
        asks: list = None,
        fill_model=None,
    ) -> Tuple[Quote, Quote]:
        if best_bid is None or best_ask is None:
            half_spread = self.config.spread / Decimal("2")
            bid_price = mid_price - half_spread
            ask_price = mid_price + half_spread
        else:
            market_spread = best_ask - best_bid

            effective_spread = min(self.config.spread, market_spread * Decimal("0.5"))

            half_spread = (
                effective_spread
                * (Decimal("1") - self.config.aggressiveness)
                / Decimal("2")
            )

            bid_price = mid_price - half_spread
            ask_price = mid_price + half_spread

        bid_size = self.config.base_size
        ask_size = self.config.base_size

        return Quote(bid_price, bid_size), Quote(ask_price, ask_size)
