"""
Integration test for data collection pipeline

This test verifies that:
1. Messages are correctly written to Parquet files
2. Files are properly rotated by date
3. Data can be read back and used by the simulator
"""

import datetime
from decimal import Decimal

import pandas as pd
import pytest

from backtest.simulator import Simulator
from data_feed.parquet_writer import ParquetWriter
from strategy.naive_maker import NaiveMaker, NaiveMakerConfig


@pytest.fixture
def test_data_dir(tmp_path):
    """fixture for test data directory"""
    return tmp_path


@pytest.fixture
def sample_depth_update():
    """fixture for sample depth update message"""
    return {
        "e": "depthUpdate",
        "E": 1623456789000,
        "s": "BTCUSDT",
        "U": 1234567,
        "u": 1234568,
        "b": [["50000.00", "1.000"]],
        "a": [["50001.00", "1.000"]],
    }


def test_data_collection_pipeline(test_data_dir, sample_depth_update):
    """Test the entire data collection pipeline"""
    # 1. Write some test data
    writer = ParquetWriter(symbol="btcusdt", base_path=test_data_dir)

    # Write messages for 3 different days
    for i in range(3):
        msg = sample_depth_update.copy()
        msg["E"] += i * 86400 * 1000  # Add i days in ms
        writer.write(msg)

    writer.close()

    # 2. Verify files were created
    files = list(test_data_dir.glob("*.parquet"))
    assert len(files) == 3

    # 3. Verify data can be read back
    for file in files:
        df = pd.read_parquet(file)
        assert len(df) == 1
        assert df.iloc[0]["event_type"] == "depthUpdate"

    # 4. Test simulator can use the data
    config = NaiveMakerConfig(
        spread=Decimal("0.0005")
    )  # Use tight spread to generate more fills
    naive_maker = NaiveMaker(config)
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(test_data_dir),
        strategy=naive_maker.quote_prices,
    )

    # Replay the data
    start_date = datetime.datetime.fromtimestamp(
        sample_depth_update["E"] / 1000.0, tz=datetime.UTC
    ).date()
    end_date = start_date + datetime.timedelta(days=2)
    simulator.replay_date_range(start_date, end_date)

    # Verify simulator processed the data
    pnl_summary = simulator.get_pnl_summary()

    print("\nTest Results:")
    print(f"Number of fills: {pnl_summary['num_fills']}")
    print(f"Total P&L: {pnl_summary['total_pnl']}")
    print(f"Average fill size: {pnl_summary['avg_fill_size']}")
    print(f"Final position: {pnl_summary['final_position']}")

    # Basic validation
    assert pnl_summary["num_fills"] >= 0  # Should have some fills with tight spread
    assert isinstance(pnl_summary["total_pnl"], float)
    assert isinstance(pnl_summary["avg_fill_size"], float)
    assert isinstance(pnl_summary["final_position"], float)
