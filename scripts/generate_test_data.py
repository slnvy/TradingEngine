"""
generate test data for integration tests
"""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path


def generate_test_data():
    """generate test data for integration tests"""
    # create test data directory
    test_data_dir = Path("tests/data/raw")
    test_data_dir.mkdir(parents=True, exist_ok=True)

    # create sample data
    data = {
        "event_type": ["depthUpdate"] * 3,
        "event_time": [1000, 2000, 3000],
        "symbol": ["btcusdt"] * 3,
        "first_update_id": [1, 2, 3],
        "final_update_id": [1, 2, 3],
        "bids": [
            ["10000.0,1.0", "9999.0,1.0"],  # first snapshot
            ["10001.0,1.0", "10000.0,1.0"],  # second snapshot
            ["10002.0,1.0", "10001.0,1.0"],  # third snapshot
        ],
        "asks": [
            ["10001.0,1.0", "10002.0,1.0"],  # first snapshot
            ["10002.0,1.0", "10003.0,1.0"],  # second snapshot
            ["10003.0,1.0", "10004.0,1.0"],  # third snapshot
        ],
    }

    # create dataframe
    df = pd.DataFrame(data)

    # convert to arrow table
    table = pa.Table.from_pandas(df)

    # write to parquet
    pq.write_table(table, test_data_dir / "btcusdt_20250610.parquet")

    # copy to 2hour sample directory
    sample_dir = test_data_dir / "2hour_sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, sample_dir / "btcusdt_20250613.parquet")


if __name__ == "__main__":
    generate_test_data() 