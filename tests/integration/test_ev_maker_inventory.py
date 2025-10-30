"""integration test for inventory skew in ev maker"""

import unittest
from decimal import Decimal

import pytest

from models.size_calculator import ScalingType, SizeConfig
from strategy.ev_maker import EVConfig, EVMaker


@pytest.mark.skip(reason="requires market data files")
class TestEVMakerInventory(unittest.TestCase):
    def setUp(self):
        """set up test fixtures"""
        # size config with both linear and sigmoid scaling
        self.linear_size_config = SizeConfig(
            base_size=Decimal("0.001"),
            max_size_mult=Decimal("3.0"),
            max_position=Decimal("1.0"),
            scaling_type=ScalingType.LINEAR,
        )

        self.sigmoid_size_config = SizeConfig(
            base_size=Decimal("0.001"),
            max_size_mult=Decimal("3.0"),
            max_position=Decimal("1.0"),
            scaling_type=ScalingType.SIGMOID,
            sigmoid_steepness=4.0,
        )

        # ev config with default values
        self.ev_config = EVConfig()

        # test points for inventory levels
        self.test_points = [
            Decimal("-1.0"),  # max short
            Decimal("-0.5"),  # partial short
            Decimal("0"),  # neutral
            Decimal("0.5"),  # partial long
            Decimal("1.0"),  # max long
        ]

        # sample market state
        self.mid_price = Decimal("50000")  # example btc price
        self.volatility = Decimal("0.01")  # 1% volatility
        self.bid_probability = Decimal("0.5")  # neutral fill probability
        self.ask_probability = Decimal("0.5")

    def test_linear_inventory_skew(self):
        """test that linear inventory skew affects quotes correctly"""
        maker = EVMaker(self.ev_config, self.linear_size_config)

        print("\ntesting linear inventory skew:")
        print("--------------------------------")

        for inv in self.test_points:
            # get quotes with inventory skew
            bid_quote, ask_quote = maker.quote_prices(
                mid_price=self.mid_price,
                volatility=self.volatility,
                bid_probability=self.bid_probability,
                ask_probability=self.ask_probability,
                inventory=inv,
            )

            print(f"\ninventory: {inv}")
            print(f"mid price: {self.mid_price}")
            print(f"bid quote: {bid_quote}")
            print(f"ask quote: {ask_quote}")
            print(f"bid size: {bid_quote.size}")
            print(f"ask size: {ask_quote.size}")
            print(f"bid/mid ratio: {bid_quote.price / self.mid_price}")
            print(f"ask/mid ratio: {ask_quote.price / self.mid_price}")

            # verify basic properties
            self.assertLess(bid_quote.price, ask_quote.price)  # no crossed quotes
            self.assertGreater(bid_quote.price, Decimal("0"))  # positive prices
            self.assertGreater(ask_quote.price, Decimal("0"))

            # verify inventory skew effects
            if inv == Decimal("-1.0"):  # max short
                # max bid size, zero ask size
                self.assertGreater(bid_quote.size, Decimal("0"))
                self.assertEqual(ask_quote.size, Decimal("0"))
                # price skew: higher bid to increase inventory
                self.assertGreater(
                    bid_quote.price / self.mid_price,
                    Decimal("0.999"),  # allow small spread
                )
            elif inv == Decimal("1.0"):  # max long
                # zero bid size, max ask size
                self.assertEqual(bid_quote.size, Decimal("0"))
                self.assertGreater(ask_quote.size, Decimal("0"))
                # price skew: lower ask to reduce inventory
                self.assertLess(
                    ask_quote.price / self.mid_price,
                    Decimal("1.001"),  # allow small spread
                )
            else:  # partial positions
                # both sizes should be positive
                self.assertGreater(bid_quote.size, Decimal("0"))
                self.assertGreater(ask_quote.size, Decimal("0"))

                if inv > 0:  # long position
                    # size skew: larger ask size to reduce inventory
                    self.assertGreater(ask_quote.size, bid_quote.size)
                elif inv < 0:  # short position
                    # size skew: larger bid size to increase inventory
                    self.assertGreater(bid_quote.size, ask_quote.size)

    def test_sigmoid_inventory_skew(self):
        """test that sigmoid inventory skew provides smoother transitions"""
        linear_maker = EVMaker(self.ev_config, self.linear_size_config)
        sigmoid_maker = EVMaker(self.ev_config, self.sigmoid_size_config)

        print("\ncomparing linear vs sigmoid inventory skew:")
        print("-------------------------------------------")

        for inv in self.test_points:
            # get quotes with both scaling types
            lin_bid, lin_ask = linear_maker.quote_prices(
                mid_price=self.mid_price,
                volatility=self.volatility,
                bid_probability=self.bid_probability,
                ask_probability=self.ask_probability,
                inventory=inv,
            )

            sig_bid, sig_ask = sigmoid_maker.quote_prices(
                mid_price=self.mid_price,
                volatility=self.volatility,
                bid_probability=self.bid_probability,
                ask_probability=self.ask_probability,
                inventory=inv,
            )

            print(f"\ninventory: {inv}")
            print("linear scaling:")
            print(f"  bid: price={lin_bid.price}, size={lin_bid.size}")
            print(f"  ask: price={lin_ask.price}, size={lin_ask.size}")
            print("sigmoid scaling:")
            print(f"  bid: price={sig_bid.price}, size={sig_bid.size}")
            print(f"  ask: price={sig_ask.price}, size={sig_ask.size}")

            # verify sigmoid provides smoother transitions
            if abs(inv) < 1:  # non-extreme positions
                if inv > 0:  # long position
                    # sigmoid should be more conservative
                    self.assertGreaterEqual(sig_bid.price, lin_bid.price)
                    self.assertLessEqual(sig_ask.price, lin_ask.price)
                elif inv < 0:  # short position
                    # sigmoid should be more conservative
                    self.assertLessEqual(sig_bid.price, lin_bid.price)
                    self.assertGreaterEqual(sig_ask.price, lin_ask.price)
            else:  # extreme positions
                # should match at extremes
                self.assertAlmostEqual(sig_bid.price, lin_bid.price, places=8)
                self.assertAlmostEqual(sig_ask.price, lin_ask.price, places=8)


if __name__ == "__main__":
    unittest.main()
