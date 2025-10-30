"""size calculator module for determining order sizes based on inventory"""

import math
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Tuple


class ScalingType(Enum):
    LINEAR = "linear"
    SIGMOID = "sigmoid"


@dataclass
class SizeConfig:
    # base order size when inventory is neutral
    base_size: Decimal = Decimal("0.001")
    # maximum order size multiplier at extreme inventory
    max_size_mult: Decimal = Decimal("3.0")
    # maximum allowed inventory position
    max_position: Decimal = Decimal("1.0")
    # type of scaling function to use
    scaling_type: ScalingType = ScalingType.LINEAR
    # sigmoid steepness (only used for sigmoid scaling)
    sigmoid_steepness: float = 4.0
    # minimum size multiplier (to prevent complete zeroing)
    min_size_mult: Decimal = Decimal("0.1")


class SizeCalculator:
    """calculates order sizes based on current inventory position

    the size logic follows these principles:
    - at neutral inventory: use base size for both sides
    - long inventory: increase ask size, decrease bid size
    - short inventory: increase bid size, decrease ask size
    - size changes are smooth and continuous
    - maintain minimum size except at extreme positions
    """

    def __init__(self, config: SizeConfig):
        self.config = config

    def _sigmoid_scale(self, x: float) -> float:
        """apply sigmoid scaling to normalized inventory

        maps [-1, 1] to [-1, 1] with smooth transitions
        """
        # scale x to get steeper sigmoid
        x = x * self.config.sigmoid_steepness
        # sigmoid function: 1 / (1 + e^-x)
        sig = 1 / (1 + math.exp(-x))
        # map [0, 1] to [-1, 1]
        return 2 * sig - 1

    def get_sizes(
        self,
        inventory: Decimal,
        side_bias: bool = True,  # if true, adjust sizes based on inventory
    ) -> Tuple[Decimal, Decimal]:
        """calculate bid and ask sizes based on inventory

        args:
            inventory: current inventory position
            side_bias: whether to adjust sizes based on inventory

        returns:
            tuple of (bid_size, ask_size)
        """
        # log for verification
        print("\nsize calculation:")
        print(f"inventory: {inventory}")
        print(f"base size: {self.config.base_size}")
        print(f"scaling type: {self.config.scaling_type.value}")

        if not side_bias:
            return self.config.base_size, self.config.base_size

        # normalize inventory to [-1, 1]
        norm_inv = float(inventory / self.config.max_position)
        if abs(norm_inv) > 1:
            norm_inv = math.copysign(1.0, norm_inv)

        # apply scaling function
        if self.config.scaling_type == ScalingType.SIGMOID:
            scaled_inv = self._sigmoid_scale(norm_inv)
            print(f"sigmoid scaled inventory: {scaled_inv}")
            # ensure sigmoid scaling stays within linear bounds
            if abs(norm_inv) >= 1:
                scaled_inv = norm_inv  # at extreme positions, match linear scaling
            elif norm_inv > 0:
                scaled_inv = min(scaled_inv, norm_inv)
            else:
                scaled_inv = max(scaled_inv, norm_inv)
        else:  # linear scaling
            scaled_inv = norm_inv
            print(f"linear scaled inventory: {scaled_inv}")

        # calculate size multipliers
        # positive inventory: increase ask mult, decrease bid mult
        # negative inventory: increase bid mult, decrease ask mult
        base_mult = (float(self.config.max_size_mult) - 1.0) / 2.0
        min_mult = float(self.config.min_size_mult)

        # adjust multipliers based on scaled inventory
        if scaled_inv > 0:  # long position
            # only zero out bid at max inventory
            if abs(scaled_inv) >= 1:
                bid_mult = 0
            else:
                bid_mult = max(min_mult, 1.0 - scaled_inv * base_mult * 2)
            ask_mult = 1.0 + scaled_inv * base_mult * 2  # increase with inventory
        else:  # short position
            bid_mult = 1.0 - scaled_inv * base_mult * 2  # increase with short position
            # only zero out ask at max short
            if abs(scaled_inv) >= 1:
                ask_mult = 0
            else:
                ask_mult = max(min_mult, 1.0 + scaled_inv * base_mult * 2)

        # apply multipliers to base size
        bid_size = self.config.base_size * Decimal(str(bid_mult))
        ask_size = self.config.base_size * Decimal(str(ask_mult))

        print(f"bid multiplier: {bid_mult}")
        print(f"ask multiplier: {ask_mult}")
        print(f"final bid size: {bid_size}")
        print(f"final ask size: {ask_size}")

        return bid_size, ask_size
