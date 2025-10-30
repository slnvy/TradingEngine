"""
parquet writer module for persisting market data

This module provides the ParquetWriter class which:
1. Creates daily Parquet files in data/raw/
2. Efficiently appends messages using PyArrow
3. Handles file rotation at UTC midnight
4. Ensures proper schema conversion
"""

import datetime
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from .schemas import DepthUpdate

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _convert_list_to_string(lst: List[List[str]]) -> List[str]:
    """Convert nested list to list of strings for better Parquet storage

    Args:
        lst: List of [price, quantity] pairs

    Returns:
        List of "price,quantity" strings
    """
    return [f"{price},{qty}" for price, qty in lst]


def _convert_string_to_list(lst: List[str]) -> List[List[str]]:
    """Convert list of strings back to nested list

    Args:
        lst: List of "price,quantity" strings

    Returns:
        List of [price, quantity] pairs
    """
    return [s.split(",") for s in lst]


class ParquetWriter:
    """Writes market data to daily Parquet files

    This class handles:
    - Daily file rotation
    - Schema conversion
    - Efficient appending
    - Resource cleanup

    Attributes:
        symbol: Trading pair symbol
        base_path: Base directory for Parquet files
        current_file: Current Parquet file being written to
        current_date: Date of current file
        writer: PyArrow writer instance
        schema: PyArrow schema for data
    """

    def __init__(self, symbol: str = "btcusdt", base_path: str = "data/raw") -> None:
        """Initialize writer

        Args:
            symbol: Trading pair symbol
            base_path: Base directory for Parquet files
        """
        self.symbol = symbol.lower()
        self.base_path = Path(base_path)
        self.current_file: Optional[str] = None
        self.current_date: Optional[datetime.date] = None
        self.writer: Optional[pq.ParquetWriter] = None

        # Create schema for Parquet files
        self.schema = pa.schema(
            [
                ("event_type", pa.string()),
                ("event_time", pa.int64()),
                ("symbol", pa.string()),
                ("first_update_id", pa.int64()),
                ("final_update_id", pa.int64()),
                (
                    "bids",
                    pa.list_(pa.string()),
                ),  # Store as list of "price,quantity" strings
                (
                    "asks",
                    pa.list_(pa.string()),
                ),  # Store as list of "price,quantity" strings
            ]
        )

        # Ensure base directory exists
        os.makedirs(self.base_path, exist_ok=True)

    def _get_file_path(self, date: datetime.date) -> Path:
        """Get Parquet file path for date

        Args:
            date: Date to get file for

        Returns:
            Path to Parquet file
        """
        date_str = date.strftime("%Y%m%d")
        filename = f"{self.symbol}_{date_str}.parquet"
        path = self.base_path / filename  # noqa: E501
        return path

    def _rotate_if_needed(self, message_time: int) -> None:
        """Rotate file if date has changed

        Args:
            message_time: Message timestamp in milliseconds
        """
        message_date = datetime.datetime.fromtimestamp(
            message_time / 1000.0, tz=datetime.UTC
        ).date()

        if message_date != self.current_date:
            # Close current file if open
            if self.writer is not None:
                self.writer.close()
                self.writer = None

            # Update file info
            self.current_date = message_date
            self.current_file = self._get_file_path(message_date)

            # Create new writer
            current_file_str = str(self.current_file)
            schema = self.schema
            compression = "snappy"
            self.writer = pq.ParquetWriter(  # noqa: E501
                current_file_str, schema=schema, compression=compression
            )
            logger.info(f"Rotated to new Parquet file: {self.current_file}")

    def write(self, message: Dict[str, Any]) -> None:
        """Write message to Parquet file

        Args:
            message: Market data message

        Raises:
            Exception: If error writing message
        """
        try:
            # Validate message
            depth_update = DepthUpdate(**message)

            # Rotate file if needed
            self._rotate_if_needed(depth_update.E)

            # Convert nested lists to strings for better storage
            bids_str = _convert_list_to_string(depth_update.b)
            asks_str = _convert_list_to_string(depth_update.a)

            # Convert to Arrow table
            table = pa.Table.from_pydict(
                {
                    "event_type": [depth_update.e],
                    "event_time": [depth_update.E],
                    "symbol": [depth_update.s],
                    "first_update_id": [depth_update.U],
                    "final_update_id": [depth_update.u],
                    "bids": [bids_str],
                    "asks": [asks_str],
                },
                schema=self.schema,
            )

            # Write to file
            self.writer.write_table(table)

        except Exception as e:
            logger.error(f"Error writing message to Parquet: {e}")
            raise

    def close(self) -> None:
        """Close current Parquet file"""
        if self.writer is not None:
            try:
                self.writer.close()
            except Exception as e:
                logger.error(f"Error closing Parquet writer: {e}")
            finally:
                self.writer = None
                self.current_file = None
                self.current_date = None
