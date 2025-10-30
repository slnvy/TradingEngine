"""
unit tests for message recorder
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from websockets.exceptions import ConnectionClosedOK

from data_feed.recorder import MessageRecorder


class MockWebSocket:
    """mock websocket for testing"""

    def __init__(self, messages=None):
        self.messages = messages or []
        self.message_index = 0
        self.closed = False
        self.subscribed = False

    async def connect(self):
        """mock connect"""
        return self

    async def disconnect(self):
        """mock disconnect"""
        self.closed = True
        self.subscribed = False

    async def subscribe(self):
        """mock subscribe"""
        self.subscribed = True

    async def unsubscribe(self):
        """mock unsubscribe"""
        self.subscribed = False

    async def receive(self):
        """mock receive messages"""
        if not self.subscribed:
            return None

        if self.message_index >= len(self.messages):
            # Simulate normal close after messages are exhausted
            self.closed = True
            raise ConnectionClosedOK(None, None)

        message = self.messages[self.message_index]
        self.message_index += 1

        if isinstance(message, Exception):
            raise message

        return message

    def is_connected(self):
        """mock connection status"""
        return not self.closed


@pytest.fixture
def mock_redis():
    """fixture for mocked redis client"""

    async def mock_xadd(stream_key, fields=None, **kwargs):
        # Ensure fields is a dict
        if fields is None:
            fields = {}
        return "message_id"

    async def mock_aclose():
        pass

    redis_mock = AsyncMock()
    redis_mock.xadd = AsyncMock(side_effect=mock_xadd)
    redis_mock.aclose = AsyncMock(side_effect=mock_aclose)
    return redis_mock


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


@pytest.mark.asyncio
async def test_recorder_initialization():
    """test recorder initialization"""
    recorder = MessageRecorder(redis_url="redis://dummy", symbol="btcusdt")
    assert recorder.symbol == "btcusdt"
    assert recorder.stream_key == "stream:lob:btcusdt"
    assert not recorder._running


@pytest.mark.asyncio
async def test_recorder_successful_message_processing(mock_redis, sample_depth_update):
    """test successful message processing"""
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        with patch("data_feed.recorder.BinanceWebSocket") as mock_ws_class:
            # Setup mock websocket
            mock_ws = MockWebSocket(messages=[sample_depth_update])
            mock_ws_class.return_value = mock_ws

            # Create recorder
            recorder = MessageRecorder()

            # Run with timeout
            try:
                await asyncio.wait_for(recorder.start(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected as the recorder runs indefinitely
            finally:
                await recorder.stop()

            # Verify Redis interactions
            mock_redis.xadd.assert_called_once()
            call_args = mock_redis.xadd.call_args

            # Verify stream key
            assert call_args[0][0] == "stream:lob:btcusdt"

            # Verify message data was passed correctly
            assert "fields" in call_args[1]
            assert "data" in call_args[1]["fields"]
            stored_data = json.loads(call_args[1]["fields"]["data"])
            assert stored_data["e"] == sample_depth_update["e"]
            assert stored_data["s"] == sample_depth_update["s"]


@pytest.mark.asyncio
async def test_recorder_connection_closed_handling(mock_redis):
    """test handling of connection closed"""
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        with patch("data_feed.recorder.BinanceWebSocket") as mock_ws_class:
            # Setup mock websocket that raises ConnectionClosedOK
            mock_ws = MockWebSocket(messages=[ConnectionClosedOK(None, None)])
            mock_ws_class.return_value = mock_ws

            # Create recorder
            recorder = MessageRecorder()

            # Run with timeout
            try:
                await asyncio.wait_for(recorder.start(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected as the recorder runs indefinitely
            finally:
                await recorder.stop()

            # Verify cleanup
            assert not recorder._running
            assert mock_redis.aclose.call_count == 1


@pytest.mark.asyncio
async def test_recorder_invalid_message_handling(mock_redis):
    """test handling of invalid messages"""
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        with patch("data_feed.recorder.BinanceWebSocket") as mock_ws_class:
            # Setup mock websocket with invalid message
            invalid_message = {"invalid": "message"}
            mock_ws = MockWebSocket(messages=[invalid_message])
            mock_ws_class.return_value = mock_ws

            # Create recorder
            recorder = MessageRecorder()

            # Run with timeout
            try:
                await asyncio.wait_for(recorder.start(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected as the recorder runs indefinitely
            finally:
                await recorder.stop()

            # Verify no messages were stored
            mock_redis.xadd.assert_not_called()


@pytest.mark.asyncio
async def test_recorder_stop(mock_redis, sample_depth_update):
    """test recorder stop functionality"""
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        with patch("data_feed.recorder.BinanceWebSocket") as mock_ws_class:
            # Setup mock websocket
            mock_ws = MockWebSocket(messages=[sample_depth_update])
            mock_ws_class.return_value = mock_ws

            # Create recorder
            recorder = MessageRecorder()

            # Run with timeout
            try:
                await asyncio.wait_for(recorder.start(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected as the recorder runs indefinitely
            finally:
                await recorder.stop()

            # Verify cleanup
            assert not recorder._running
            assert mock_redis.aclose.call_count == 1


@pytest.mark.asyncio
async def test_recorder_redis_connection_error():
    """test handling of redis connection errors"""
    with patch("redis.asyncio.from_url", side_effect=RedisConnectionError):
        with pytest.raises(RedisConnectionError):
            MessageRecorder(redis_url="redis://invalid")


@pytest.mark.asyncio
async def test_recorder_redis_maxlen(mock_redis, sample_depth_update):
    """test redis stream maxlen enforcement"""
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        with patch("data_feed.recorder.BinanceWebSocket") as mock_ws_class:
            # Setup mock websocket
            mock_ws = MockWebSocket(messages=[sample_depth_update])
            mock_ws_class.return_value = mock_ws

            # Create recorder
            recorder = MessageRecorder()

            # Run with timeout
            try:
                await asyncio.wait_for(recorder.start(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected as the recorder runs indefinitely
            finally:
                await recorder.stop()

            # Verify maxlen was set
            call_args = mock_redis.xadd.call_args
            assert "maxlen" in call_args[1]
            assert call_args[1]["maxlen"] == 100000


@pytest.mark.asyncio
async def test_recorder_concurrent_writes(mock_redis, sample_depth_update):
    """test concurrent writes to redis stream"""
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        with patch("data_feed.recorder.BinanceWebSocket") as mock_ws_class:
            # Setup mock websocket with multiple messages
            messages = [sample_depth_update] * 3
            mock_ws = MockWebSocket(messages=messages)
            mock_ws_class.return_value = mock_ws

            # Create recorder
            recorder = MessageRecorder()

            # Run with timeout
            try:
                await asyncio.wait_for(recorder.start(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Expected as the recorder runs indefinitely
            finally:
                await recorder.stop()

            # Verify all messages were written
            assert mock_redis.xadd.call_count == 3

            # Verify messages were written in order
            calls = mock_redis.xadd.call_args_list
            for i, call in enumerate(calls):
                stored_data = json.loads(call[1]["fields"]["data"])
                assert stored_data == sample_depth_update
