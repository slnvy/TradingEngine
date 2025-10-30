"""
Manual test script for Binance WebSocket client.

This script connects to Binance WebSocket, prints 10 depth updates,
and exits cleanly. Used for quick verification of functionality.
"""

import asyncio
import logging

from data_feed.binance_ws import BinanceWebSocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Connect to Binance WebSocket and print 10 depth updates."""
    ws = BinanceWebSocket()
    await ws.connect()
    await ws.subscribe()
    count = 0
    try:
        while count < 10:
            msg = await ws.receive()
            if msg:
                logger.info("Received message: %s", msg)
                count += 1
    finally:
        await ws.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
