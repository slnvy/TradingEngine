"""
backtest regression test for ev maker with inventory skew

this test:
1. runs backtest with and without inventory skew
2. compares P&L and risk metrics
3. verifies inventory management behavior
"""

import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from backtest.simulator import Simulator
from models.inventory_skew import InventorySkewConfig
from models.size_calculator import ScalingType, SizeConfig
from strategy.ev_maker import EVConfig, EVMaker


def run_backtest(
    data_path: Path,
    ev_config: EVConfig,
    size_config: SizeConfig,
    start_date: datetime.date,
    end_date: datetime.date,
) -> dict:
    """run backtest with given configuration

    args:
        data_path: path to data directory
        ev_config: ev maker configuration
        size_config: size calculator configuration
        start_date: start date for backtest
        end_date: end date for backtest

    returns:
        dictionary with backtest results
    """
    # create ev maker instance
    maker = EVMaker(ev_config, size_config)

    # create simulator
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(data_path),
        strategy=maker.quote_prices,
    )

    # run backtest
    simulator.replay_date_range(start_date, end_date)

    # get results
    fills_df = simulator.get_fills_df()
    pnl_summary = simulator.get_pnl_summary()

    # calculate pnl std and running position from fills
    if len(fills_df) > 0:
        # calculate fill PNL
        fills_df["fill_pnl"] = fills_df.apply(
            lambda x: (
                float(x["price"] * x["size"])
                if x["side"] == "sell"
                else float(-x["price"] * x["size"])
            ),
            axis=1,
        )
        pnl_std = float(fills_df["fill_pnl"].std())

        # calculate running position
        fills_df["position_delta"] = fills_df.apply(
            lambda x: float(x["size"]) if x["side"] == "buy" else float(-x["size"]),
            axis=1,
        )
        fills_df["position"] = fills_df["position_delta"].cumsum()
        position_excursion = float(fills_df["position"].abs().max())
        final_position = float(fills_df["position"].iloc[-1])
    else:
        pnl_std = 0.0
        position_excursion = 0.0
        final_position = 0.0

    return {
        "total_pnl": pnl_summary["total_pnl"],
        "pnl_std": pnl_std,
        "position_excursion": position_excursion,
        "final_position": final_position,
        "num_fills": len(fills_df),
    }


@pytest.mark.backtest_regression
def test_inventory_skew_regression():
    """test that inventory skew improves risk metrics without degrading P&L"""
    # set up test data path
    data_path = Path("data/raw")
    assert data_path.exists(), f"Test data not found at {data_path}"

    # create configurations - use smaller sizes for faster testing
    base_size_config = SizeConfig(
        base_size=Decimal("0.0001"),  # smaller base size for testing
        max_size_mult=Decimal("2.0"),  # 2x size at max inventory
        max_position=Decimal("0.01"),  # 0.01 btc max position
        scaling_type=ScalingType.SIGMOID,  # smoother transitions
        sigmoid_steepness=4.0,  # moderate steepness
    )

    # baseline config with minimal inventory skew
    baseline_inventory_config = InventorySkewConfig(
        max_position=0.01,  # 0.01 btc max position
        skew_factor=0.1,  # very light skew
        min_spread_bps=1.0,  # 1 bps minimum spread for more fills
        spread_factor=0.1,  # minimal spread increase
        continuity_clip=0.1,  # max 0.10 move per side
    )
    baseline_ev_config = EVConfig(inventory_config=baseline_inventory_config)

    # inventory-aware config with stronger skew
    inventory_skew_config = InventorySkewConfig(
        max_position=0.01,  # 0.01 btc max position
        skew_factor=2.0,  # strong skew
        min_spread_bps=1.0,  # 1 bps minimum spread for more fills
        spread_factor=2.0,  # significant spread increase
        continuity_clip=0.1,  # max 0.10 move per side
    )
    inventory_ev_config = EVConfig(inventory_config=inventory_skew_config)

    # set up test period - use smaller sample file
    start_date = datetime.date(2025, 6, 12)  # matches moderate sample file
    end_date = start_date  # single day test

    # run backtests
    print("\nRunning baseline backtest (minimal inventory skew)...")
    baseline_results = run_backtest(
        data_path=data_path,
        ev_config=baseline_ev_config,
        size_config=base_size_config,
        start_date=start_date,
        end_date=end_date,
    )

    print("\nRunning inventory-aware backtest (strong skew)...")
    inventory_results = run_backtest(
        data_path=data_path,
        ev_config=inventory_ev_config,
        size_config=base_size_config,
        start_date=start_date,
        end_date=end_date,
    )

    # print results
    print("\nBacktest Results:")
    print("\nBaseline (Minimal Inventory Skew):")
    for k, v in baseline_results.items():
        print(f"  {k}: {v}")

    print("\nInventory-Aware (Strong Skew):")
    for k, v in inventory_results.items():
        print(f"  {k}: {v}")

    # verify risk improvements (only meaningful if we have fills)
    if baseline_results["num_fills"] > 0 or inventory_results["num_fills"] > 0:
        assert (
            inventory_results["position_excursion"]
            <= baseline_results["position_excursion"] + 0.001  # small tolerance
        ), "Inventory skew should reduce position excursions"

        assert (
            abs(inventory_results["final_position"])
            <= abs(baseline_results["final_position"]) + 0.001
        ), "Inventory skew should reduce end-of-day positions"

        if baseline_results["pnl_std"] > 0:
            assert (
                inventory_results["pnl_std"] <= baseline_results["pnl_std"] * 1.2
            ), "Inventory skew should not increase P&L volatility by more than 20%"
    else:
        print("No fills generated - testing system functionality only")

    # verify P&L is not severely impacted (only if we have baseline P&L)
    if baseline_results["total_pnl"] != 0:
        pnl_degradation = (
            baseline_results["total_pnl"] - inventory_results["total_pnl"]
        ) / abs(baseline_results["total_pnl"])
        assert (
            pnl_degradation <= 0.2
        ), "Inventory skew should not reduce P&L by more than 20%"
    else:
        print("No baseline P&L to compare - both strategies generated 0 fills")

    # export results to CSV
    results_df = pd.DataFrame(
        {
            "metric": list(baseline_results.keys()),
            "baseline": list(baseline_results.values()),
            "inventory_aware": list(inventory_results.values()),
        }
    )
    results_df.to_csv("backtest_results.csv", index=False)
    print("\nResults exported to backtest_results.csv")
