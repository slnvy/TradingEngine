"""
unit tests for live trading engine
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from live.engine import LiveEngine


class TestLiveEngine:
    """test cases for live engine"""

    @pytest.fixture
    def sample_message(self):
        """sample depth update message"""
        return {
            "e": "depthUpdate",
            "E": 1627846261000,
            "s": "BTCUSDT",
            "U": 1627846261,
            "u": 1627846261,
            "b": [["50000.00", "1.000"], ["49999.00", "2.000"]],
            "a": [["50001.00", "1.500"], ["50002.00", "0.500"]],
        }

    @pytest.mark.asyncio
    async def test_engine_initialization(self):
        """test that engine initializes correctly"""
        engine = LiveEngine(symbol="btcusdt")

        assert engine.symbol == "btcusdt"
        assert engine.stream_key == "depth_updates:btcusdt"
        assert engine.position_key == "position:btcusdt"
        assert engine.pnl_key == "pnl:btcusdt"
        assert engine.current_inventory == Decimal("0")
        assert not engine.running
        assert engine.gateway is None
        assert engine.current_bid_order_id is None
        assert engine.current_ask_order_id is None

        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_initialization_with_credentials(self):
        """test that engine initializes with binance credentials"""
        engine = LiveEngine(
            symbol="btcusdt", api_key="test_key", api_secret="test_secret", testnet=True
        )

        assert engine.api_key == "test_key"
        assert engine.api_secret == "test_secret"
        assert engine.testnet is True

        await engine.stop()

    @pytest.mark.asyncio
    async def test_process_message(self, sample_message):
        """test message processing generates quotes"""
        engine = LiveEngine(symbol="btcusdt")

        # prepare mock message fields
        message_fields = {b"data": json.dumps(sample_message).encode()}

        # capture stdout
        with patch("builtins.print") as mock_print:
            await engine._process_message(message_fields)

            # verify quote was printed (multiple calls due to debug output)
            assert mock_print.call_count > 0

            # check that the final call contains the quote
            final_call = mock_print.call_args_list[-1]
            output = final_call[0][0]
            assert "quote:" in output
            assert "bid=" in output
            assert "ask=" in output
            assert "mid=" in output

        await engine.stop()

    @pytest.mark.asyncio
    async def test_process_message_with_gateway(self, sample_message):
        """test message processing with binance gateway"""
        engine = LiveEngine(
            symbol="btcusdt", api_key="test_key", api_secret="test_secret"
        )

        # Mock the gateway
        mock_gateway = AsyncMock()
        engine.gateway = mock_gateway

        # prepare mock message fields
        message_fields = {b"data": json.dumps(sample_message).encode()}

        # Mock the order management
        with patch.object(
            engine, "_manage_orders", new_callable=AsyncMock
        ) as mock_manage:
            with patch("builtins.print") as mock_print:
                await engine._process_message(message_fields)

                # verify quote was printed
                assert mock_print.call_count > 0

                # verify order management was called
                mock_manage.assert_called_once()

        await engine.stop()

    @pytest.mark.asyncio
    async def test_process_empty_message(self, sample_message):
        """test handling of empty bid/ask message"""
        engine = LiveEngine(symbol="btcusdt")

        empty_message = sample_message.copy()
        empty_message["b"] = []
        empty_message["a"] = []

        message_fields = {b"data": json.dumps(empty_message).encode()}

        with patch("builtins.print") as mock_print:
            await engine._process_message(message_fields)

            # should not print quote for empty message
            mock_print.assert_not_called()

        await engine.stop()

    @pytest.mark.asyncio
    async def test_engine_start_stop(self):
        """test engine start and stop lifecycle"""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            engine = LiveEngine(symbol="btcusdt")

            # test that engine can be stopped without starting
            await engine.stop()

            # verify redis connection was closed
            mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_engine_initialization_redis_state(self):
        """test engine initializes redis state correctly"""
        engine = LiveEngine(symbol="btcusdt")

        # Mock the redis client
        mock_redis = AsyncMock()
        mock_redis.exists.side_effect = [False, False]  # position and pnl don't exist
        engine.redis_client = mock_redis

        await engine._initialize_redis_state()

        # verify redis keys were initialized
        mock_redis.set.assert_any_call("position:btcusdt", "0")
        mock_redis.set.assert_any_call("pnl:btcusdt", "0")

    @pytest.mark.asyncio
    async def test_fill_processing(self):
        """test fill processing updates position and pnl"""
        engine = LiveEngine(symbol="btcusdt")

        # Mock the redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"10.0"
        engine.redis_client = mock_redis

        # Mock the trade data
        trade = {
            "id": "123",
            "isBuyer": True,
            "price": "50000.00",
            "qty": "0.001",
            "commission": "0.05",
            "commissionAsset": "USDT",
        }

        await engine._process_fill(trade)

        # verify inventory was updated
        assert engine.current_inventory == Decimal("0.001")

        # verify redis was updated
        mock_redis.set.assert_any_call("position:btcusdt", "0.001")
        # pnl should be updated (10.0 - 0.05 commission)
        mock_redis.set.assert_any_call("pnl:btcusdt", "9.95")

    @pytest.mark.asyncio
    async def test_fill_checking_processes_new_trades(self):
        """test fill checking processes new trades only"""
        engine = LiveEngine(symbol="btcusdt")

        # Mock the gateway
        mock_gateway = AsyncMock()
        engine.gateway = mock_gateway
        engine.last_trade_id = 100

        # Mock the trades
        trades = [
            {
                "id": "100",
                "isBuyer": True,
                "price": "50000",
                "qty": "0.001",
                "commission": "0.05",
            },
            {
                "id": "101",
                "isBuyer": False,
                "price": "50100",
                "qty": "0.001",
                "commission": "0.05",
            },
        ]
        mock_gateway.get_account_trades.return_value = trades

        with patch.object(engine, "_process_fill") as mock_process:
            await engine._check_for_fills()

        # should only process the new trade (id 101)
        mock_process.assert_called_once_with(trades[1])
        assert engine.last_trade_id == 101

    @pytest.mark.asyncio
    async def test_fill_listener_integration(self):
        """test that fill checking is integrated into main loop"""
        engine = LiveEngine(symbol="btcusdt")

        # Mock the gateway
        mock_gateway = AsyncMock()
        engine.gateway = mock_gateway

        # Mock the market data message
        message_data = {
            "e": "depthUpdate",
            "E": 1234567890,
            "s": "BTCUSDT",
            "U": 1,
            "u": 2,
            "b": [["50000.00", "1.0"]],
            "a": [["50100.00", "1.0"]],
        }

        fields = {b"data": json.dumps(message_data).encode()}

        # Mock successful order placement
        mock_gateway.post_order.return_value = {"orderId": "12345"}

        with patch.object(engine, "_check_for_fills") as mock_check_fills:
            await engine._process_message(fields)

        # verify fill checking was called
        mock_check_fills.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_position_and_pnl_keys_update_on_fill(self):
        """test redis position and pnl keys update on fill - task 7.3 requirement"""
        engine = LiveEngine(symbol="btcusdt")

        # Mock the redis client
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"5.0"  # existing pnl
        engine.redis_client = mock_redis

        # Simulate a buy fill
        trade = {
            "id": "123",
            "isBuyer": True,
            "price": "50000.00",
            "qty": "0.002",
            "commission": "0.10",
            "commissionAsset": "USDT",
        }

        await engine._process_fill(trade)

        # verify position key was updated
        mock_redis.set.assert_any_call("position:btcusdt", "0.002")

        # verify pnl key was updated (5.0 - 0.10 commission)
        mock_redis.set.assert_any_call("pnl:btcusdt", "4.90")
