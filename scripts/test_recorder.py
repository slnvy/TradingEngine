"""
Test script to run the recorder and verify Redis stream.

This script:
1. Connects to Binance WebSocket
2. Records messages to Redis stream
3. Verifies messages are being written correctly
4. Exits cleanly on Ctrl+C
"""

import asyncio
import json
import logging
import signal
import sys
from typing import NoReturn

import redis.asyncio as redis

from data_feed.recorder import MessageRecorder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def verify_redis_stream(redis_client: redis.Redis, stream_key: str) -> None:
    """Verify messages are being written to Redis stream.

    Args:
        redis_client: Redis client
        stream_key: Stream key to monitor
    """
    last_id = "0-0"
    while True:
        try:
            # Read new messages
            messages = await redis_client.xread(
                streams={stream_key: last_id},
                count=1,
                block=1000,
            )

            if messages:
                # Update last_id for next read
                stream_messages = messages[0][1]
                for message_id, fields in stream_messages:
                    last_id = message_id
                    data = json.loads(fields[b"data"])
                    logger.info(
                        "Received message: %s (ID: %s)",
                        data["s"],
                        message_id,
                    )

        except Exception as e:
            logger.error("Error reading from Redis: %s", e)
            break


def handle_signal(signum: int, frame: None) -> NoReturn:
    """Handle Ctrl+C signal.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info("Stopping recorder...")
    sys.exit(0)


async def main() -> None:
    """Run the recorder and verify Redis stream."""
    # Create recorder and Redis client
    recorder = MessageRecorder(symbol="btcusdt")
    redis_client = redis.from_url("redis://localhost:6379")

    # Set up signal handler
    signal.signal(signal.SIGINT, handle_signal)

    try:
        logger.info("Starting recorder... Press Ctrl+C to stop")
        # Run recorder and verification in parallel
        await asyncio.gather(
            recorder.start(),
            verify_redis_stream(redis_client, recorder.stream_key),
        )
    except Exception as e:
        logger.error("Error: %s", e)
    finally:
        await recorder.stop()
        await redis_client.close()
        logger.info("Recorder stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
