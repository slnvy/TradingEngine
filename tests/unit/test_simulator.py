"""
test module for simulator

this module contains tests for the Simulator class which:
1. verifies correct replay of parquet data
2. ensures deterministic order book state
3. tests error handling and edge cases
"""

import datetime
from decimal import Decimal

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from pyarrow import Table, schema

from backtest.simulator import Simulator
from lob.order_book import OrderBook
from strategy.naive_maker import NaiveMaker, NaiveMakerConfig


@pytest.fixture
def test_data_dir(tmp_path):
    """create temporary directory with test parquet files"""
    data_dir = tmp_path / "data" / "raw"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def sample_messages():
    """create sample market data messages"""
    return [
        {
            "event_type": "depthUpdate",
            "event_time": 1234567890000,
            "symbol": "btcusdt",
            "first_update_id": 1,
            "final_update_id": 1,
            "bids": ["100.0,1.0", "99.0,2.0"],
            "asks": ["101.0,1.0", "102.0,2.0"],
        },
        {
            "event_type": "depthUpdate",
            "event_time": 1234567890001,
            "symbol": "btcusdt",
            "first_update_id": 2,
            "final_update_id": 2,
            "bids": ["100.0,2.0", "99.0,1.0"],
            "asks": ["101.0,2.0", "102.0,1.0"],
        },
    ]


@pytest.fixture
def sample_parquet_file(test_data_dir, sample_messages):
    """create sample parquet file with test data"""
    # create schema
    sch = schema(
        [
            ("event_type", pa.string()),
            ("event_time", pa.int64()),
            ("symbol", pa.string()),
            ("first_update_id", pa.int64()),
            ("final_update_id", pa.int64()),
            ("bids", pa.list_(pa.string())),
            ("asks", pa.list_(pa.string())),
        ]
    )

    # create table
    table = Table.from_pylist(sample_messages, schema=sch)

    # write to parquet
    date = datetime.date(2024, 1, 1)
    file_path = test_data_dir / f"btcusdt_{date.strftime('%Y%m%d')}.parquet"
    pq.write_table(table, file_path)

    return file_path


def test_simulator_initialization(test_data_dir):
    """test simulator initialization"""
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(test_data_dir),
        strategy=naive_maker.quote_prices,
    )
    assert simulator.symbol == "btcusdt"
    assert simulator.data_path == test_data_dir
    assert simulator.strategy == naive_maker.quote_prices


def test_simulator_custom_order_book(test_data_dir):
    """test simulator with custom order book"""
    order_book = OrderBook()
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(test_data_dir),
        strategy=naive_maker.quote_prices,
    )
    simulator.order_book = order_book
    assert simulator.order_book == order_book


def test_replay_date(sample_parquet_file):
    """test replaying messages for a single date"""
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(sample_parquet_file.parent),
        strategy=naive_maker.quote_prices,
    )
    date = datetime.date(2024, 1, 1)
    simulator.replay_date(date)

    # verify order book state includes both market and strategy orders
    bids, asks = simulator.get_order_book_state()
    assert len(bids) >= 2  # market orders + strategy orders
    assert len(asks) >= 2
    assert ["100.0", "2.0"] in bids  # market order
    assert ["101.0", "2.0"] in asks  # market order


def test_replay_date_range(test_data_dir, sample_parquet_file):
    """test replaying messages for a date range"""
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(test_data_dir),
        strategy=naive_maker.quote_prices,
    )
    start_date = datetime.date(2024, 1, 1)
    end_date = datetime.date(2024, 1, 1)
    simulator.replay_date_range(start_date, end_date)

    # verify order book state includes both market and strategy orders
    bids, asks = simulator.get_order_book_state()
    assert len(bids) >= 2  # market orders + strategy orders
    assert len(asks) >= 2
    assert ["100.0", "2.0"] in bids  # market order
    assert ["101.0", "2.0"] in asks  # market order


def test_replay_missing_file(test_data_dir):
    """test handling of missing parquet files"""
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(test_data_dir),
        strategy=naive_maker.quote_prices,
    )
    date = datetime.date(2024, 1, 1)

    # should not raise exception
    simulator.replay_date_range(date, date)

    # verify order book is empty
    bids, asks = simulator.get_order_book_state()
    assert len(bids) == 0
    assert len(asks) == 0


def test_deterministic_state(sample_parquet_file):
    """test that replay produces deterministic order book state"""
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator1 = Simulator(
        symbol="btcusdt",
        data_path=str(sample_parquet_file.parent),
        strategy=naive_maker.quote_prices,
    )
    simulator2 = Simulator(
        symbol="btcusdt",
        data_path=str(sample_parquet_file.parent),
        strategy=naive_maker.quote_prices,
    )

    date = datetime.date(2024, 1, 1)
    simulator1.replay_date(date)
    simulator2.replay_date(date)

    # verify both simulators have identical state
    assert simulator1.get_order_book_state() == simulator2.get_order_book_state()


def test_naive_maker_integration(tmp_path):
    """test naive maker integration with simulator

    this test:
    1. creates a test parquet file with market data
    2. runs simulator with naive maker
    3. verifies fills and P&L tracking
    """
    # create test data directory
    data_dir = tmp_path / "data" / "raw"
    data_dir.mkdir(parents=True)

    # create test parquet file
    test_data = {
        "event_type": ["depthUpdate"] * 3,
        "event_time": [1000, 2000, 3000],
        "symbol": ["btcusdt"] * 3,
        "first_update_id": [1, 2, 3],
        "final_update_id": [1, 2, 3],
        "bids": [
            ["10000.0,1.0", "9999.0,1.0"],  # first snapshot
            ["10001.0,1.0", "10000.0,1.0"],  # second snapshot - our bid should fill
            ["10002.0,1.0", "10001.0,1.0"],  # third snapshot - our ask should fill
        ],
        "asks": [
            ["10001.0,1.0", "10002.0,1.0"],
            ["10002.0,1.0", "10003.0,1.0"],
            ["10003.0,1.0", "10004.0,1.0"],
        ],
    }

    # write to parquet
    df = pd.DataFrame(test_data)
    date = datetime.date(2024, 1, 1)
    file_path = data_dir / f"btcusdt_{date.strftime('%Y%m%d')}.parquet"
    df.to_parquet(file_path)

    # run simulator with naive maker
    naive_maker = NaiveMaker(NaiveMakerConfig())
    simulator = Simulator(
        symbol="btcusdt",
        data_path=str(data_dir),
        strategy=naive_maker.quote_prices,
        spread=Decimal("0.001"),  # 0.1% spread
    )

    simulator.replay_date(date)

    # verify fills and P&L
    fills_df = simulator.get_fills_df()
    assert len(fills_df) > 0  # should have some fills
    assert simulator.pnl != 0  # should have non-zero P&L


def test_backtest_produces_pnl_csv(tmp_path):
    """test that backtest run produces a basic P&L CSV file"""
    # create test data directory
    data_dir = tmp_path / "data" / "raw"
    data_dir.mkdir(parents=True)

    # create test parquet file
    test_data = {
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

    df = pd.DataFrame(test_data)
    test_file = data_dir / "btcusdt_20240101.parquet"
    df.to_parquet(test_file)

    # run simulator with naive maker
    naive_maker = NaiveMaker(NaiveMakerConfig())
    sim = Simulator(
        symbol="btcusdt",
        data_path=str(data_dir),
        strategy=naive_maker.quote_prices,
        spread=Decimal("1.0"),  # spread matches book spread
    )

    # replay test data
    sim.replay_date(datetime.date(2024, 1, 1))

    # get P&L summary and export to CSV
    pnl_summary = sim.get_pnl_summary()
    pnl_csv_path = tmp_path / "pnl_summary.csv"
    pd.DataFrame([pnl_summary]).to_csv(pnl_csv_path, index=False)

    # verify that the CSV file exists and contains expected columns
    assert pnl_csv_path.exists()
    pnl_df = pd.read_csv(pnl_csv_path)
    expected_columns = ["num_fills", "final_position", "total_pnl"]
    for col in expected_columns:
        assert col in pnl_df.columns
