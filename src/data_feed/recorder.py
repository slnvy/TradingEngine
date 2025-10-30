"""
message recorder module for writing websocket messages to redis stream

This module provides the MessageRecorder class which:
1. Connects to a Binance WebSocket stream for market data
2. Validates incoming messages using schemas
3. Writes valid messages to Redis stream and Parquet files
"""

import asyncio
import json
import logging
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

import redis.asyncio as redis
from websockets.exceptions import ConnectionClosedOK

from .binance_ws import BinanceWebSocket
from .parquet_writer import ParquetWriter
from .schemas import DepthUpdate

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s - %(name)s - " "%(levelname)s - %(message)s"),
)
logger = logging.getLogger(__name__)


class MessageRecorder:
    """Records WebSocket messages to Redis stream and Parquet files

    This class handles:
    - Connection to Binance WebSocket
    - Message validation
    - Writing to Redis stream
    - Writing to Parquet files
    - Proper cleanup of resources

    Attributes:
        redis_client: Redis client for stream operations
        symbol: Trading pair symbol being recorded
        ws_client: WebSocket client for market data
        stream_key: Redis stream key for storing messages
        parquet_writer: Writer for Parquet files
        _running: Internal flag for controlling the recording loop
        _cleanup_done: Internal flag for preventing double cleanup
        timeout: Optional timeout in seconds
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        symbol: str = "btcusdt",
        timeout: Optional[int] = None,
        output_path: str = "data/raw",
    ) -> None:
        """Initialize recorder

        Args:
            redis_url: Redis connection URL
            symbol: Trading pair symbol to record
            timeout: Optional timeout in seconds
            output_path: Path to write Parquet files
        """
        self.redis_client = redis.from_url(redis_url)
        self.symbol = symbol.lower()
        self.ws_client = BinanceWebSocket(symbol=self.symbol)
        self.stream_key = f"stream:lob:{self.symbol}"
        self.parquet_writer = ParquetWriter(symbol=self.symbol, base_path=output_path)
        self._running = False
        self._cleanup_done = False
        self.timeout = timeout
        self._start_time = None

    async def start(self) -> None:
        """Start recording messages from WebSocket to Redis and Parquet

        This method:
        1. Connects to the WebSocket
        2. Subscribes to the depth stream
        3. Processes messages until stopped or timeout
        4. Handles cleanup on error

        Raises:
            Exception: If connection fails or error during processing
        """
        try:
            # connect to websocket
            await self.ws_client.connect()
            await self.ws_client.subscribe()

            self._running = True
            self._start_time = time.time()
            logger.info(f"Started recording {self.symbol} depth updates")

            # record messages until stopped or timeout
            while self._running and self.ws_client.is_connected():
                # Check timeout
                if self.timeout and time.time() - self._start_time > self.timeout:
                    logger.info(f"Timeout of {self.timeout} seconds reached")
                    break

                try:
                    message = await self.ws_client.receive()

                    if not message:
                        continue

                    # validate and parse message
                    try:
                        depth_update = DepthUpdate(**message)
                        await self._record_message(asdict(depth_update))
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        continue

                except ConnectionClosedOK:
                    logger.info("WebSocket connection closed normally")
                    break
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    break

        except Exception as e:
            logger.error(f"Error in recorder: {e}")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop recording and cleanup resources

        This method:
        1. Stops the recording loop
        2. Unsubscribes from WebSocket
        3. Closes WebSocket connection
        4. Closes Redis connection
        5. Closes Parquet writer
        """
        if self._cleanup_done:
            return

        self._running = False

        if self.ws_client:
            try:
                await self.ws_client.unsubscribe()
                await self.ws_client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from WebSocket: {e}")

        if self.redis_client:
            try:
                await self.redis_client.aclose()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

        if self.parquet_writer:
            try:
                self.parquet_writer.close()
            except Exception as e:
                logger.error(f"Error closing Parquet writer: {e}")

        self._cleanup_done = True
        logger.info("Stopped recording messages")

    async def _record_message(self, message: Dict[str, Any]) -> None:
        """Record message to Redis stream and Parquet file

        Args:
            message: Validated message data to record

        Raises:
            Exception: If error writing message
        """
        try:
            # write to redis stream
            json_data = json.dumps(message)
            stream_key = self.stream_key
            fields = {"data": json_data}
            maxlen = 100000  # keep last 100k messages
            await self.redis_client.xadd(  # noqa: E501
                stream_key,
                fields=fields,
                maxlen=maxlen,
            )

            # write to parquet
            self.parquet_writer.write(message)

        except Exception as e:
            logger.error(f"Error recording message: {e}")
            raise


async def main() -> None:
    """Main function for testing the recorder"""
    import argparse

    parser = argparse.ArgumentParser(description="Record market data")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    parser.add_argument(
        "--output-path",
        type=str,
        default="data/raw",
        help="Path to write Parquet files",
    )
    args = parser.parse_args()

    recorder = MessageRecorder(timeout=args.timeout, output_path=args.output_path)
    try:
        await recorder.start()
    except KeyboardInterrupt:
        logger.info("Stopping recorder...")
    finally:
        await recorder.stop()


if __name__ == "__main__":
    asyncio.run(main())
