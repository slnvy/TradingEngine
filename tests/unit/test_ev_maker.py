"""
unit tests for ev maker strategy
"""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, Mock

from models.fill_prob import FillProbabilityModel
from models.size_calculator import ScalingType, SizeConfig
from strategy.ev_maker import EVConfig, EVMaker


class TestEVMaker(unittest.TestCase):
    """test cases for ev maker strategy"""

    def setUp(self):
        """set up test fixtures"""
        self.mid_price = Decimal("50000")
        self.volatility = Decimal("0.01")  # 1% volatility
        self.bid_probability = Decimal("0.5")  # neutral fill probability
        self.ask_probability = Decimal("0.5")
        self.bids = [["49990", "1.0"], ["49980", "2.0"]]
        self.asks = [["50010", "1.0"], ["50020", "2.0"]]
        self.fill_model = MagicMock(spec=FillProbabilityModel)

        # Create default configs
        self.size_config = SizeConfig(
            base_size=Decimal("0.001"),
            max_size_mult=Decimal("3.0"),
            max_position=Decimal("1.0"),
            scaling_type=ScalingType.LINEAR,
        )
        self.ev_config = EVConfig()

    def test_quote_prices_min_spread(self):
        """test that quotes maintain minimum spread"""
        # mock fill model to return high probabilities
        self.fill_model.predict.side_effect = [
            0.8
        ] * 20  # 10 points for bid side + 10 for ask side

        maker = EVMaker(self.ev_config, self.size_config)
        bid_quote, ask_quote = maker.quote_prices(
            mid_price=self.mid_price,
            volatility=self.volatility,
            bid_probability=self.bid_probability,
            ask_probability=self.ask_probability,
            fill_model=self.fill_model,
        )

        # verify spread is maintained
        self.assertGreaterEqual(
            ask_quote.price - bid_quote.price, self.ev_config.min_spread
        )
        self.assertEqual(bid_quote.size, self.size_config.base_size)
        self.assertEqual(ask_quote.size, self.size_config.base_size)

    def test_quote_prices_ev_optimization(self):
        """test that quotes optimize expected value"""
        # mock fill model to return different probabilities for each price point
        # for 3 bid points: closest to mid gets highest prob, further gets lower
        # for 3 ask points: closest to mid gets lowest prob, further gets higher
        self.fill_model.predict.side_effect = [0.9, 0.5, 0.1, 0.1, 0.5, 0.9]

        # Configure for fewer points
        ev_config = EVConfig(num_points=3)  # fewer points for faster test
        maker = EVMaker(ev_config, self.size_config)

        bid_quote, ask_quote = maker.quote_prices(
            mid_price=self.mid_price,
            volatility=self.volatility,
            bid_probability=self.bid_probability,
            ask_probability=self.ask_probability,
            fill_model=self.fill_model,
        )

        # verify bid is closer to mid (higher prob)
        self.assertLess(
            abs(bid_quote.price - self.mid_price), abs(ask_quote.price - self.mid_price)
        )

    def test_quote_prices_size(self):
        """test that quote sizes are correct"""
        # mock fill model to return high probabilities
        self.fill_model.predict.side_effect = [
            0.8
        ] * 20  # 10 points for bid side + 10 for ask side

        # Configure for custom base size
        size_config = SizeConfig(
            base_size=Decimal("0.002"),
            max_size_mult=Decimal("3.0"),
            max_position=Decimal("1.0"),
            scaling_type=ScalingType.LINEAR,
        )
        maker = EVMaker(self.ev_config, size_config)

        bid_quote, ask_quote = maker.quote_prices(
            mid_price=self.mid_price,
            volatility=self.volatility,
            bid_probability=self.bid_probability,
            ask_probability=self.ask_probability,
            fill_model=self.fill_model,
        )

        self.assertEqual(bid_quote.size, Decimal("0.002"))
        self.assertEqual(ask_quote.size, Decimal("0.002"))

    def test_inventory_parameter(self):
        """test that inventory parameter is handled correctly"""
        # mock fill probability model
        fill_model = Mock()
        fill_model.predict.return_value = 0.5

        maker = EVMaker(self.ev_config, self.size_config)

        # test with different inventory values
        test_inventories = [
            Decimal("-1.0"),
            Decimal("0"),
            Decimal("0.5"),
            Decimal("1.0"),
        ]

        for inv in test_inventories:
            # should not raise any errors
            bid_quote, ask_quote = maker.quote_prices(
                mid_price=self.mid_price,
                volatility=self.volatility,
                bid_probability=self.bid_probability,
                ask_probability=self.ask_probability,
                fill_model=fill_model,
                inventory=inv,
            )

            # basic validation
            self.assertGreater(ask_quote.price, bid_quote.price)  # no crossed quotes
            self.assertGreater(bid_quote.price, Decimal("0"))  # positive prices
            self.assertGreater(ask_quote.price, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
