"""
unit tests for parquet writer
"""

import datetime

import pandas as pd
import pytest

from data_feed.parquet_writer import ParquetWriter


def _convert_array_to_list(arr):
    return [x.split(",") for x in arr.tolist()]


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


def test_parquet_writer_initialization(test_data_dir):
    """test parquet writer initialization"""
    writer = ParquetWriter(symbol="btcusdt", base_path=test_data_dir)
    assert writer.symbol == "btcusdt"
    assert writer.base_path == test_data_dir
    assert writer.writer is None
    assert writer.current_file is None
    assert writer.current_date is None


def test_message_persistence(test_data_dir, sample_depth_update):
    """test message is correctly written to parquet"""
    writer = ParquetWriter(base_path=test_data_dir)
    writer.write(sample_depth_update)
    writer.close()
    expected_date = datetime.datetime.fromtimestamp(
        sample_depth_update["E"] / 1000.0, tz=datetime.UTC
    ).date()
    file_path = test_data_dir / (f"btcusdt_{expected_date.strftime('%Y%m%d')}.parquet")
    df = pd.read_parquet(file_path)
    assert len(df) == 1
    assert df.iloc[0]["event_type"] == sample_depth_update["e"]
    assert df.iloc[0]["event_time"] == sample_depth_update["E"]
    assert df.iloc[0]["symbol"] == sample_depth_update["s"]
    assert df.iloc[0]["first_update_id"] == sample_depth_update["U"]
    assert df.iloc[0]["final_update_id"] == sample_depth_update["u"]
    stored_bids = _convert_array_to_list(df.iloc[0]["bids"])
    stored_asks = _convert_array_to_list(df.iloc[0]["asks"])
    assert stored_bids == sample_depth_update["b"]
    assert stored_asks == sample_depth_update["a"]


def test_invalid_message_handling(test_data_dir):
    """test handling of invalid messages"""
    writer = ParquetWriter(base_path=test_data_dir)

    # Try to write invalid message
    invalid_message = {"invalid": "message"}
    with pytest.raises(Exception):
        writer.write(invalid_message)

    # Verify no file was created
    assert len(list(test_data_dir.glob("*.parquet"))) == 0

    writer.close()


def test_file_rotation(test_data_dir, sample_depth_update):
    """test parquet file rotation"""
    writer = ParquetWriter(base_path=test_data_dir)
    # Write message for day 1
    writer.write(sample_depth_update)
    # Write message for next day
    next_day = sample_depth_update.copy()
    next_day["E"] += 86400 * 1000  # add one day in ms
    writer.write(next_day)
    writer.close()
    files = list(test_data_dir.glob("*.parquet"))
    assert len(files) == 2


def test_close(test_data_dir, sample_depth_update):
    """test closing parquet writer"""
    writer = ParquetWriter(base_path=test_data_dir)
    writer.write(sample_depth_update)
    writer.close()

    # Verify writer is cleaned up
    assert writer.writer is None
    assert writer.current_file is None
    assert writer.current_date is None
