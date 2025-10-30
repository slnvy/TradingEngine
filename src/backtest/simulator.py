"""
simulator module for replaying market data into order book

this module provides the Simulator class which:
1. reads parquet files containing market data
2. replays messages into the order book
3. maintains deterministic state for backtesting
4. tracks fills and P&L for strategy evaluation
"""

import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
import pyarrow.parquet as pq
from pyarrow import Table

from data_feed.schemas import DepthUpdate
from lob.order_book import Order, OrderBook

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Fill:
    """represents a filled order

    Attributes:
        timestamp: time of fill
        side: buy or sell
        price: fill price
        size: fill size
        order_id: id of filled order
    """

    timestamp: int
    side: str
    price: Decimal
    size: Decimal
    order_id: str


def _convert_string_to_list(lst: List[str]) -> List[List[str]]:
    """convert list of strings back to nested list

    Args:
        lst: list of "price,quantity" strings

    Returns:
        list of [price, quantity] pairs
    """
    return [s.split(",") for s in lst]


class Simulator:
    """replays market data into order book for backtesting

    this class handles:
    - reading parquet files
    - replaying messages in order
    - maintaining order book state
    - tracking fills and updates
    - running strategy and tracking P&L

    Attributes:
        symbol: trading pair symbol
        data_path: path to parquet files
        order_book: order book instance
        current_file: current parquet file being read
        current_date: date of current file
        fills: list of fills
        position: current position
        pnl: current P&L
        spread: fixed spread for naive maker
    """

    def __init__(
        self,
        symbol: str,
        data_path: str,
        strategy: Callable,
        spread: Decimal = Decimal("0.001"),
    ) -> None:
        """initialize simulator

        Args:
            symbol: trading pair symbol
            data_path: path to parquet files
            strategy: strategy function to use for quoting
            spread: fixed spread for naive maker
        """
        self.symbol = symbol.lower()
        self.data_path = Path(data_path)
        self.strategy = strategy
        self.spread = spread
        self.order_book = OrderBook()
        self.current_file: Optional[str] = None
        self.current_date: Optional[datetime.date] = None
        self.fills: List[Fill] = []
        self.position: Decimal = Decimal("0")
        self.pnl: Decimal = Decimal("0")
        self.volatility: Decimal = Decimal("0.01")  # 1% default volatility

    def _get_file_path(self, date: datetime.date) -> Path:
        """get parquet file path for date

        Args:
            date: date to get file for

        Returns:
            path to parquet file
        """
        date_str = date.strftime("%Y%m%d")
        filename = f"{self.symbol}_{date_str}.parquet"
        path = self.data_path / filename
        return path

    def _read_parquet_file(self, file_path: Path) -> Table:
        """read parquet file into arrow table

        Args:
            file_path: path to parquet file

        Returns:
            arrow table containing messages

        Raises:
            FileNotFoundError: if file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"parquet file not found: {file_path}")

        return pq.read_table(file_path)

    def _process_message(self, message: Dict) -> None:
        """process single message into order book

        Args:
            message: market data message
        """
        # Map Parquet/test fields to DepthUpdate fields
        mapped = {
            "e": message.get("event_type", "depthUpdate"),
            "E": message.get("event_time"),
            "s": message.get("symbol"),
            "U": message.get("first_update_id"),
            "u": message.get("final_update_id"),
            "b": _convert_string_to_list(message.get("bids", [])),
            "a": _convert_string_to_list(message.get("asks", [])),
        }
        depth_update = DepthUpdate(**mapped)

        # Store our quotes before clearing
        our_quotes = []
        for price, orders in self.order_book.bids.items():
            for order in orders:
                if order.order_id.startswith("strat_"):
                    our_quotes.append(order)
        for price, orders in self.order_book.asks.items():
            for order in orders:
                if order.order_id.startswith("strat_"):
                    our_quotes.append(order)

        # Clear and update the order book
        self.order_book.bids.clear()
        self.order_book.asks.clear()

        for price, qty in depth_update.b:
            price_dec = Decimal(price)
            qty_dec = Decimal(qty)
            self.order_book.bids[price_dec] = [
                Order(
                    order_id=f"mkt_{price}_{qty}",  # prefix with mkt_ to distinguish
                    side="buy",
                    price=price_dec,
                    size=qty_dec,
                    timestamp=depth_update.E,
                )
            ]
        for price, qty in depth_update.a:
            price_dec = Decimal(price)
            qty_dec = Decimal(qty)
            self.order_book.asks[price_dec] = [
                Order(
                    order_id=f"mkt_{price}_{qty}",  # prefix with mkt_ to distinguish
                    side="sell",
                    price=price_dec,
                    size=qty_dec,
                    timestamp=depth_update.E,
                )
            ]

        # Restore our quotes (they might get filled in _run_strategy)
        for order in our_quotes:
            if order.side == "buy":
                if order.price not in self.order_book.bids:
                    self.order_book.bids[order.price] = []
                self.order_book.bids[order.price].append(order)
            else:
                if order.price not in self.order_book.asks:
                    self.order_book.asks[order.price] = []
                self.order_book.asks[order.price].append(order)

        # Run strategy
        self._run_strategy(depth_update.E)

    def _run_strategy(self, timestamp: int) -> None:
        """run strategy and simulate fills"""
        # Get current best bid/ask
        best_bid = self.order_book.get_best_bid()
        best_ask = self.order_book.get_best_ask()
        if not best_bid or not best_ask:
            return

        # Calculate mid price (best_bid and best_ask are already Decimal prices)
        mid_price = (best_bid + best_ask) / 2

        # Get current book state for fill probability
        bids = [[str(p), str(o[0].size)] for p, o in self.order_book.bids.items()]
        asks = [[str(p), str(o[0].size)] for p, o in self.order_book.asks.items()]

        # Get strategy quotes
        quotes = self.strategy(
            mid_price=mid_price,
            volatility=self.volatility,
            bid_probability=Decimal("0.5"),  # neutral fill probability
            ask_probability=Decimal("0.5"),  # neutral fill probability
            inventory=self.position,
            best_bid=best_bid,
            best_ask=best_ask,
            bids=bids,
            asks=asks,
        )

        # Unpack quotes
        bid_quote, ask_quote = quotes
        bid_price, bid_size = bid_quote.price, bid_quote.size
        ask_price, ask_size = ask_quote.price, ask_quote.size

        # Place strategy orders
        bid_order = Order(
            order_id=f"strat_bid_{timestamp}",
            side="buy",
            price=bid_price,
            size=bid_size,
            timestamp=timestamp,
        )
        ask_order = Order(
            order_id=f"strat_ask_{timestamp}",
            side="sell",
            price=ask_price,
            size=ask_size,
            timestamp=timestamp,
        )

        # Check for fills against market orders
        for price, orders in self.order_book.asks.items():
            for order in orders:
                if not order.order_id.startswith("mkt_"):
                    continue
                if bid_price >= order.price:  # our bid crosses their ask
                    self._simulate_fill(
                        timestamp=timestamp,
                        side="buy",
                        price=order.price,
                        size=min(order.size, bid_order.size),
                    )
                    return  # only one fill per update

        for price, orders in self.order_book.bids.items():
            for order in orders:
                if not order.order_id.startswith("mkt_"):
                    continue
                if ask_price <= order.price:  # our ask crosses their bid
                    self._simulate_fill(
                        timestamp=timestamp,
                        side="sell",
                        price=order.price,
                        size=min(order.size, ask_order.size),
                    )
                    return  # only one fill per update

        # Add our orders to the book if not filled
        if bid_price not in self.order_book.bids:
            self.order_book.bids[bid_price] = []
        self.order_book.bids[bid_price].append(bid_order)

        if ask_price not in self.order_book.asks:
            self.order_book.asks[ask_price] = []
        self.order_book.asks[ask_price].append(ask_order)

    def _simulate_fill(
        self, timestamp: int, side: str, price: Decimal, size: Decimal
    ) -> None:
        """simulate fill and update position/pnl

        Args:
            timestamp: fill timestamp
            side: buy or sell
            price: fill price
            size: fill size
        """
        # Create fill record
        fill = Fill(
            timestamp=timestamp,
            side=side,
            price=price,
            size=size,
            order_id=f"{side}_{timestamp}",
        )
        self.fills.append(fill)

        # Update position
        if side == "buy":
            self.position += size
        else:
            self.position -= size

        # Update P&L (convert to Decimal for consistent arithmetic)
        fill_value = price * size
        if side == "sell":
            self.pnl = self.pnl + fill_value
        else:
            self.pnl = self.pnl - fill_value

    def replay_date(self, date: datetime.date) -> None:
        """replay messages for a single date

        Args:
            date: date to replay

        Raises:
            FileNotFoundError: if parquet file doesn't exist
        """
        file_path = self._get_file_path(date)
        table = self._read_parquet_file(file_path)
        df = table.to_pandas()

        for _, row in df.iterrows():
            self._process_message(row)

    def replay_date_range(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> None:
        """replay messages for a date range

        Args:
            start_date: start date (inclusive)
            end_date: end date (inclusive)

        Raises:
            FileNotFoundError: if any parquet file doesn't exist
        """
        current_date = start_date
        while current_date <= end_date:
            try:
                self.replay_date(current_date)
            except FileNotFoundError as e:
                logger.warning(f"skipping missing file: {e}")
            current_date += datetime.timedelta(days=1)

    def get_order_book_state(self) -> Tuple[List[List[str]], List[List[str]]]:
        """get current order book state

        Returns:
            tuple of (bids, asks) where each is a list of [price, quantity] pairs
        """
        return self.order_book.get_snapshot()

    def get_fills_df(self) -> pd.DataFrame:
        """get fills as a pandas DataFrame

        Returns:
            DataFrame with columns: timestamp, side, price, size, order_id
        """
        return pd.DataFrame([vars(fill) for fill in self.fills])

    def get_pnl_summary(self) -> Dict[str, float]:
        """get pnl summary statistics

        Returns:
            dictionary with summary statistics
        """
        fills_df = self.get_fills_df()
        if len(fills_df) == 0:
            return {
                "num_fills": 0,
                "total_pnl": 0.0,
                "avg_fill_size": 0.0,
                "final_position": float(self.position),
            }

        avg_fill_size = float(fills_df["size"].mean())
        return {
            "num_fills": len(fills_df),
            "total_pnl": float(self.pnl),
            "avg_fill_size": avg_fill_size,
            "final_position": float(self.position),
        }
