"""
unit tests for binance websocket client
"""

import asyncio
import json

import pytest
from websockets.exceptions import ConnectionClosedOK

from data_feed.binance_ws import BinanceWebSocket


class MockWebSocket:
    def __init__(self, recv_data=None):
        self.sent = []
        self.recv_data = recv_data or []
        self.closed = False
        self.recv_calls = 0

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        if self.recv_calls < len(self.recv_data):
            data = self.recv_data[self.recv_calls]
            self.recv_calls += 1
            return data
        await asyncio.sleep(0.01)
        return None

    async def close(self):
        self.closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()


@pytest.fixture
def mock_websocket():
    ws = MockWebSocket()
    return ws


def test_binance_ws_initialization():
    ws = BinanceWebSocket(symbol="btcusdt")
    assert ws.symbol == "btcusdt"
    assert ws.ws is None
    assert not ws._running


@pytest.mark.asyncio
async def test_binance_ws_connect(monkeypatch):
    """test websocket connection"""

    async def mock_connect(*args, **kwargs):
        return MockWebSocket()

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    assert ws.ws is not None


@pytest.mark.asyncio
async def test_binance_ws_disconnect(monkeypatch):
    """test websocket disconnection"""

    async def mock_connect(*args, **kwargs):
        return MockWebSocket()

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    await ws.disconnect()
    assert ws.ws is None


@pytest.mark.asyncio
async def test_binance_ws_subscribe(monkeypatch):
    """test websocket subscription"""

    async def mock_connect(*args, **kwargs):
        return MockWebSocket()

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    await ws.subscribe()
    # no exception means pass


@pytest.mark.asyncio
async def test_binance_ws_unsubscribe(monkeypatch):
    """test websocket unsubscription"""

    async def mock_connect(*args, **kwargs):
        return MockWebSocket()

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    await ws.unsubscribe()
    # no exception means pass


@pytest.mark.asyncio
async def test_binance_ws_receive(monkeypatch):
    """test websocket message reception"""
    test_message = {
        "e": "depthUpdate",
        "E": 1234567890000,
        "s": "BTCUSDT",
        "U": 1234567,
        "u": 1234568,
        "b": [["50000.00", "1.000"]],
        "a": [["50001.00", "1.000"]],
    }

    async def mock_connect(*args, **kwargs):
        return MockWebSocket([json.dumps(test_message)])

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    message = await ws.receive()
    assert message == test_message


@pytest.mark.asyncio
async def test_binance_ws_receive_connection_closed(monkeypatch):
    """test websocket connection closed handling"""

    class ClosedWebSocket(MockWebSocket):
        async def recv(self):
            raise ConnectionClosedOK(None, None)

    async def mock_connect(*args, **kwargs):
        return ClosedWebSocket()

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    message = await ws.receive()
    assert message is None


@pytest.mark.asyncio
async def test_binance_ws_receive_invalid_json(monkeypatch):
    """test websocket invalid json handling"""

    async def mock_connect(*args, **kwargs):
        return MockWebSocket(["invalid json"])

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    await ws.connect()
    message = await ws.receive()
    assert message is None


@pytest.mark.asyncio
async def test_binance_ws_is_connected(monkeypatch):
    """test websocket connection status"""

    async def mock_connect(*args, **kwargs):
        return MockWebSocket()

    monkeypatch.setattr("websockets.client.connect", mock_connect)
    ws = BinanceWebSocket()
    assert not ws.is_connected()
    await ws.connect()
    assert ws.is_connected()
    await ws.disconnect()
    assert not ws.is_connected()
