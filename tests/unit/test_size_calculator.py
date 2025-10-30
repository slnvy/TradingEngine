"""unit tests for size calculator"""

import unittest
from decimal import Decimal

from models.size_calculator import ScalingType, SizeCalculator, SizeConfig


class TestSizeCalculator(unittest.TestCase):
    def setUp(self):
        """set up test fixtures"""
        self.base_size = Decimal("0.001")
        self.max_size_mult = Decimal("3.0")
        self.max_position = Decimal("1.0")

        # linear config
        self.linear_config = SizeConfig(
            base_size=self.base_size,
            max_size_mult=self.max_size_mult,
            max_position=self.max_position,
            scaling_type=ScalingType.LINEAR,
        )

        # sigmoid config
        self.sigmoid_config = SizeConfig(
            base_size=self.base_size,
            max_size_mult=self.max_size_mult,
            max_position=self.max_position,
            scaling_type=ScalingType.SIGMOID,
            sigmoid_steepness=4.0,
        )

    def test_neutral_inventory(self):
        """test that neutral inventory gives base size on both sides"""
        calc = SizeCalculator(self.linear_config)
        bid_size, ask_size = calc.get_sizes(Decimal("0"))

        self.assertEqual(bid_size, self.base_size)
        self.assertEqual(ask_size, self.base_size)

    def test_max_long_inventory(self):
        """test size adjustment at max long position"""
        calc = SizeCalculator(self.linear_config)
        bid_size, ask_size = calc.get_sizes(self.max_position)

        # at max long: min bid size, max ask size
        self.assertEqual(bid_size, Decimal("0"))
        self.assertEqual(ask_size, self.base_size * self.max_size_mult)

    def test_max_short_inventory(self):
        """test size adjustment at max short position"""
        calc = SizeCalculator(self.linear_config)
        bid_size, ask_size = calc.get_sizes(-self.max_position)

        # at max short: max bid size, min ask size
        self.assertEqual(bid_size, self.base_size * self.max_size_mult)
        self.assertEqual(ask_size, Decimal("0"))

    def test_partial_inventory(self):
        """test size adjustment at partial inventory"""
        calc = SizeCalculator(self.linear_config)
        bid_size, ask_size = calc.get_sizes(Decimal("0.5"))

        # at 50% long: expect aggressive size adjustment
        # bid size reduced to minimum (0.1 * base_size)
        # ask size increased to 2.0 * base_size
        self.assertAlmostEqual(
            bid_size,
            self.base_size * Decimal("0.1"),
            places=8,
        )
        self.assertAlmostEqual(
            ask_size,
            self.base_size * Decimal("2.0"),
            places=8,
        )

    def test_side_bias_disabled(self):
        """test that side_bias=False returns base size regardless of inventory"""
        calc = SizeCalculator(self.linear_config)

        for inv in [Decimal("-1"), Decimal("0"), Decimal("1")]:
            bid_size, ask_size = calc.get_sizes(inv, side_bias=False)
            self.assertEqual(bid_size, self.base_size)
            self.assertEqual(ask_size, self.base_size)

    def test_sigmoid_scaling(self):
        """test that sigmoid scaling produces smoother transitions"""
        linear_calc = SizeCalculator(self.linear_config)
        sigmoid_calc = SizeCalculator(self.sigmoid_config)

        # test points
        test_points = [
            Decimal("-1.0"),
            Decimal("-0.75"),
            Decimal("-0.5"),
            Decimal("-0.25"),
            Decimal("0"),
            Decimal("0.25"),
            Decimal("0.5"),
            Decimal("0.75"),
            Decimal("1.0"),
        ]

        print("\ncomparing linear vs sigmoid scaling:")
        for inv in test_points:
            lin_bid, lin_ask = linear_calc.get_sizes(inv)
            sig_bid, sig_ask = sigmoid_calc.get_sizes(inv)

            print(f"\ninventory: {inv}")
            print(f"linear - bid: {lin_bid}, ask: {lin_ask}")
            print(f"sigmoid - bid: {sig_bid}, ask: {sig_ask}")

            # verify sigmoid sizes are between base size and linear sizes
            if abs(inv) >= 1:
                # at extreme positions, sigmoid should match linear
                self.assertEqual(sig_bid, lin_bid)
                self.assertEqual(sig_ask, lin_ask)
            elif inv > 0:
                # for positive inventory, sigmoid should be more conservative
                self.assertGreaterEqual(sig_bid, lin_bid)
                self.assertLessEqual(sig_ask, lin_ask)
            elif inv < 0:
                # for negative inventory, sigmoid should be more conservative
                self.assertLessEqual(sig_bid, lin_bid)
                self.assertGreaterEqual(sig_ask, lin_ask)
            else:
                # at neutral inventory, both should match
                self.assertEqual(sig_bid, lin_bid)
                self.assertEqual(sig_ask, lin_ask)


if __name__ == "__main__":
    unittest.main()
