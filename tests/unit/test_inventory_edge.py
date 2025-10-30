"""unit tests for inventory edge cases"""

import unittest
from decimal import Decimal

from models.inventory_skew import InventorySkew, InventorySkewConfig
from models.size_calculator import ScalingType, SizeCalculator, SizeConfig


class TestInventoryEdgeCases(unittest.TestCase):
    def setUp(self):
        """set up test fixtures"""
        # inventory skew config with moderate settings
        self.inventory_config = InventorySkewConfig(
            max_position=1.0,  # 1 btc max position
            skew_factor=1.0,  # moderate skew
            min_spread_bps=1.0,  # 1 bps minimum spread
            spread_factor=1.0,  # linear spread increase
            continuity_clip=0.05,  # max 0.05 move per side
        )

        # size config with sigmoid scaling
        self.size_config = SizeConfig(
            base_size=Decimal("0.001"),  # 0.001 btc base size
            max_size_mult=Decimal("3.0"),  # 3x size at max inventory
            max_position=Decimal("1.0"),  # 1 btc max position
            scaling_type=ScalingType.SIGMOID,  # smoother transitions
            sigmoid_steepness=4.0,  # moderate steepness
        )

        # test points for edge cases
        self.test_points = [
            Decimal("-1.0"),  # max short
            Decimal("-0.9"),  # near max short
            Decimal("-0.5"),  # partial short
            Decimal("0"),  # neutral
            Decimal("0.5"),  # partial long
            Decimal("0.9"),  # near max long
            Decimal("1.0"),  # max long
        ]

        # sample market state
        self.mid_price = Decimal("50000")  # example btc price

    def test_inventory_skew_edges(self):
        """test inventory skew behavior at edge cases"""
        skew = InventorySkew(self.inventory_config)

        print("\ntesting inventory skew at edge cases:")
        print("-------------------------------------")

        prev_bid = None
        prev_ask = None

        for inv in self.test_points:
            # get skewed prices
            bid, ask = skew.apply_skew(float(self.mid_price), float(inv))

            print(f"\ninventory: {inv}")
            print(f"bid: {bid}")
            print(f"ask: {ask}")
            print(f"spread: {ask - bid}")
            print(f"mid shift: {(bid + ask)/2 - float(self.mid_price)}")

            # verify basic properties
            self.assertLess(bid, ask)  # no crossed quotes
            self.assertGreater(bid, 0)  # positive prices
            self.assertGreater(ask, 0)

            # verify continuity with floating point tolerance
            if prev_bid is not None:
                bid_move = abs(bid - prev_bid)
                ask_move = abs(ask - prev_ask)
                self.assertLessEqual(
                    bid_move, self.inventory_config.continuity_clip + 1e-10
                )
                self.assertLessEqual(
                    ask_move, self.inventory_config.continuity_clip + 1e-10
                )

            prev_bid = bid
            prev_ask = ask

    def test_size_calculator_edges(self):
        """test size calculator behavior at edge cases"""
        calc = SizeCalculator(self.size_config)

        print("\ntesting size calculator at edge cases:")
        print("--------------------------------------")

        prev_bid_size = None
        prev_ask_size = None

        for inv in self.test_points:
            # get adjusted sizes
            bid_size, ask_size = calc.get_sizes(inv)

            print(f"\ninventory: {inv}")
            print(f"bid size: {bid_size}")
            print(f"ask size: {ask_size}")

            # verify basic properties
            self.assertGreaterEqual(bid_size, 0)  # non-negative sizes
            self.assertGreaterEqual(ask_size, 0)

            # verify size adjustments
            if inv == Decimal("-1.0"):  # max short
                self.assertEqual(ask_size, 0)  # no asks at max short
                self.assertGreater(
                    bid_size, self.size_config.base_size
                )  # increased bid size
            elif inv == Decimal("1.0"):  # max long
                self.assertEqual(bid_size, 0)  # no bids at max long
                self.assertGreater(
                    ask_size, self.size_config.base_size
                )  # increased ask size
            else:  # partial positions
                self.assertGreater(bid_size, 0)  # both sides active
                self.assertGreater(ask_size, 0)

                if inv > 0:  # long bias
                    self.assertGreater(ask_size, bid_size)  # larger asks
                elif inv < 0:  # short bias
                    self.assertGreater(bid_size, ask_size)  # larger bids

            # verify smooth transitions with larger allowance for size changes
            if prev_bid_size is not None:
                bid_change = abs(bid_size - prev_bid_size)
                ask_change = abs(ask_size - prev_ask_size)
                max_size_change = self.size_config.base_size * Decimal(
                    "1.0"
                )  # allow larger changes
                self.assertLessEqual(bid_change, max_size_change)
                self.assertLessEqual(ask_change, max_size_change)

            prev_bid_size = bid_size
            prev_ask_size = ask_size
