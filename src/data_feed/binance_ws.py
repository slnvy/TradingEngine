"""
binance websocket client module

This module provides the BinanceWebSocket class which:
1. Connects to Binance's WebSocket API
2. Handles different venues (GLOBAL, VISION, US, TEST)
3. Manages depth stream subscriptions
4. Handles connection lifecycle and cleanup
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import websockets.client
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedOK,
    InvalidStatusCode,
)

# configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Binance WebSocket endpoints by venue
BASE_URLS: Dict[str, str] = {
    "GLOBAL": "wss://stream.binance.com:9443/ws",
    "VISION": "wss://data-stream.binance.vision/ws",
    "US": "wss://stream.binance.us:9443/ws",
    "TEST": "wss://stream.testnet.binance.vision/ws",
}


def build_depth_url(symbol: str, venue: str = "VISION") -> str:
    """Build WebSocket URL for depth stream

    Args:
        symbol: Trading pair symbol
        venue: Binance venue (GLOBAL, VISION, US, TEST)

    Returns:
        WebSocket URL for depth stream

    Raises:
        KeyError: If venue is not recognized
    """
    symbol = symbol.lower()
    base = BASE_URLS[venue.upper()]
    return f"{base}/{symbol}@depth"


class BinanceWebSocket:
    """Binance WebSocket client for depth updates

    This class handles:
    - Connection to different Binance venues
    - Depth stream subscription
    - Message receiving with validation
    - Connection lifecycle and cleanup

    Attributes:
        symbol: Trading pair symbol being monitored
        ws: WebSocket connection
        message_count: Number of messages received
        max_messages: Maximum messages before auto-disconnect
        _running: Internal flag for controlling the receive loop
        venue: Binance venue to connect to
    """

    def __init__(self, symbol: str = "btcusdt") -> None:
        """Initialize WebSocket client

        Args:
            symbol: Trading pair symbol (default: btcusdt)
        """
        self.symbol = symbol.lower()
        self.ws = None
        self.message_count = 0
        self.max_messages = 1024  # Maximum streams per connection
        self._running = False
        self.venue = os.getenv("BINANCE_VENUE", "VISION")

    async def connect(self) -> None:
        """Connect to Binance WebSocket stream

        This method:
        1. Tries venues in order of preference
        2. Handles connection timeouts
        3. Handles HTTP 451 errors

        Raises:
            RuntimeError: If no venues are available
            Exception: For other connection errors
        """
        # Try venues in order of preference
        venues = [self.venue] if self.venue else ["VISION", "US", "GLOBAL"]

        last_error = None
        for venue in venues:
            try:
                depth_url = build_depth_url(self.symbol, venue)
                logger.info(f"Attempting to connect to {venue} venue: {depth_url}")

                self.ws = await asyncio.wait_for(
                    websockets.client.connect(depth_url), timeout=5
                )
                self._running = True
                logger.info(
                    f"Connected to Binance WebSocket ({venue}) for {self.symbol}"
                )
                return

            except InvalidStatusCode as e:
                if e.status_code == 451:
                    logger.warning(
                        f"Venue {venue} blocked (HTTP 451), trying next venue"
                    )
                    last_error = e
                    continue
                raise
            except Exception as e:
                logger.error(f"Error connecting to {venue}: {e}")
                last_error = e
                continue

        # If we get here, all venues failed
        error_msg = "No Binance endpoint available (all venues failed)"
        if last_error:
            error_msg += f": {str(last_error)}"
        raise RuntimeError(error_msg)

    async def disconnect(self) -> None:
        """Disconnect from WebSocket

        This method:
        1. Stops the receive loop
        2. Closes the WebSocket connection
        3. Cleans up resources
        """
        self._running = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.ws = None
                logger.info("Disconnected from Binance WebSocket")

    async def receive(self) -> Optional[Dict[str, Any]]:
        """Receive message from WebSocket

        This method:
        1. Receives raw message
        2. Handles ping/pong
        3. Validates message format

        Returns:
            Dict with message data if valid
            None if connection closed or invalid message

        Raises:
            Exception: For unexpected errors
        """
        if not self.ws:
            return None

        try:
            while self._running:
                message = await self.ws.recv()

                if not message:
                    continue

                data = json.loads(message)

                # Handle ping/pong
                if "ping" in data:
                    await self.ws.pong(data["ping"])
                    continue

                # Validate message has required fields
                if not all(k in data for k in ["e", "E", "s", "U", "u", "b", "a"]):
                    logger.warning(f"Received invalid message format: {data}")
                    continue

                self.message_count += 1
                return data

        except ConnectionClosedOK:
            logger.info("WebSocket connection closed normally")
            return None
        except ConnectionClosed as e:
            logger.error(f"WebSocket connection closed unexpectedly: {e}")
            return None
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            return None

    async def subscribe(self) -> None:
        """subscribe to depth stream"""
        subscribe_message = {
            "method": "SUBSCRIBE",
            "params": [f"{self.symbol}@depth"],
            "id": 1,
        }
        await self.ws.send(json.dumps(subscribe_message))
        logger.info(f"Subscribed to {self.symbol} depth stream")

    async def unsubscribe(self) -> None:
        """unsubscribe from depth stream"""
        unsubscribe_message = {
            "method": "UNSUBSCRIBE",
            "params": [f"{self.symbol}@depth"],
            "id": 1,
        }
        await self.ws.send(json.dumps(unsubscribe_message))
        logger.info(f"Unsubscribed from {self.symbol} depth stream")

    def is_connected(self) -> bool:
        """Check if websocket is connected"""
        return self.ws is not None and self._running


async def main():
    """Main function for testing the websocket client"""
    ws = BinanceWebSocket()
    try:
        await ws.connect()
        await ws.subscribe()
        while ws.is_connected():
            msg = await ws.receive()
            if msg:
                print(msg)
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        await ws.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
