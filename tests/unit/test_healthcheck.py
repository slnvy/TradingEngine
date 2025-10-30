"""
tests for healthcheck metrics functionality
"""

from unittest.mock import AsyncMock, patch

import pytest

from live.healthcheck import HealthcheckMetrics, HealthcheckServer


@pytest.fixture
def mock_redis():
    """mock redis client for testing"""
    mock = AsyncMock()
    mock.get = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def metrics(mock_redis):
    """create healthcheck metrics with mocked redis"""
    metrics = HealthcheckMetrics()
    metrics.redis_client = mock_redis
    return metrics


class TestHealthcheckMetrics:
    """test healthcheck metrics functionality"""

    @pytest.mark.asyncio
    async def test_metrics_initialization(self):
        """test metrics are properly initialized"""
        metrics = HealthcheckMetrics(symbol="btcusdt")

        # verify metrics exist
        assert hasattr(metrics, "engine_loop_latency")
        assert hasattr(metrics, "outstanding_orders")
        assert hasattr(metrics, "current_inventory")
        assert hasattr(metrics, "current_pnl")
        assert hasattr(metrics, "engine_loops_total")
        assert hasattr(metrics, "fills_total")

        # verify registry is custom
        assert metrics.registry is not None

        await metrics.close()

    def test_record_engine_loop(self, metrics):
        """test engine loop recording"""
        initial_count = metrics.engine_loops_total._value._value
        metrics.record_engine_loop(0.5)

        # verify counter incremented
        assert metrics.engine_loops_total._value._value == initial_count + 1

    def test_record_fill(self, metrics):
        """test fill recording"""
        initial_count = metrics.fills_total.labels(side="buy")._value._value
        metrics.record_fill("buy")

        # verify counter incremented
        assert metrics.fills_total.labels(side="buy")._value._value == initial_count + 1

    @pytest.mark.asyncio
    async def test_update_outstanding_orders(self, metrics):
        """test outstanding orders update"""
        await metrics.update_outstanding_orders(2, 3)

        # verify gauge values
        buy_gauge = metrics.outstanding_orders.labels(side="buy")
        sell_gauge = metrics.outstanding_orders.labels(side="sell")

        assert buy_gauge._value._value == 2
        assert sell_gauge._value._value == 3

    @pytest.mark.asyncio
    async def test_update_position_metrics(self, metrics, mock_redis):
        """test position and pnl metrics update from redis"""
        # mock redis responses
        mock_redis.get.side_effect = [b"1.5", b"150.75"]  # position, pnl

        await metrics.update_position_metrics()

        # verify redis was called
        mock_redis.get.assert_any_call("position:btcusdt")
        mock_redis.get.assert_any_call("pnl:btcusdt")

        # verify gauge values
        assert metrics.current_inventory._value._value == 1.5
        assert metrics.current_pnl._value._value == 150.75

    @pytest.mark.asyncio
    async def test_update_position_metrics_redis_error(self, metrics, mock_redis):
        """test position metrics update handles redis errors gracefully"""
        # mock redis to raise exception
        mock_redis.get.side_effect = Exception("redis error")

        # should not raise exception
        await metrics.update_position_metrics()

    @pytest.mark.asyncio
    async def test_get_metrics(self, metrics, mock_redis):
        """test metrics export"""
        # mock redis responses
        mock_redis.get.side_effect = [b"0.5", b"25.50"]

        metrics_data = await metrics.get_metrics()

        # verify it returns bytes (prometheus format)
        assert isinstance(metrics_data, bytes)

        # verify it contains expected metric names
        metrics_str = metrics_data.decode()
        assert "engine_loop_latency_seconds" in metrics_str
        assert "outstanding_orders_total" in metrics_str
        assert "current_inventory" in metrics_str
        assert "current_pnl" in metrics_str

    @pytest.mark.asyncio
    async def test_close(self, metrics, mock_redis):
        """test cleanup"""
        await metrics.close()
        mock_redis.aclose.assert_called_once()


class TestHealthcheckServer:
    """test healthcheck server functionality"""

    @pytest.mark.asyncio
    async def test_server_initialization(self, metrics):
        """test server initialization"""
        server = HealthcheckServer(metrics, port=8001)

        assert server.metrics == metrics
        assert server.port == 8001
        assert server.server is None

    @pytest.mark.asyncio
    async def test_metrics_endpoint_content(self, metrics):
        """test metrics endpoint returns correct content type and data"""
        server = HealthcheckServer(metrics)

        # mock request (not used in current implementation)
        mock_request = None

        with patch.object(metrics, "get_metrics", return_value=b"test_metrics_data"):
            status, headers, body = await server.handle_metrics(mock_request)

        assert status == 200
        assert "Content-Type" in headers
        assert body == b"test_metrics_data"

    @pytest.mark.asyncio
    async def test_health_endpoint(self, metrics):
        """test health endpoint"""
        server = HealthcheckServer(metrics)

        # mock request
        mock_request = None

        status, headers, body = await server.handle_health(mock_request)

        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert body == b'{"status": "ok"}'

    @pytest.mark.asyncio
    async def test_prometheus_can_scrape_metrics(self, metrics):
        """test that prometheus can scrape /metrics endpoint - task 8.1 requirement"""
        # record some metrics to ensure data is available
        metrics.record_engine_loop(0.015)
        await metrics.update_outstanding_orders(1, 1)
        metrics.record_fill("buy")

        server = HealthcheckServer(metrics)

        # test metrics endpoint
        status, headers, body = await server.handle_metrics(None)

        # verify prometheus can scrape this format
        assert status == 200
        assert "text/plain" in headers["Content-Type"]

        metrics_text = body.decode()

        # verify required metrics are present for task 8.1
        assert "engine_loop_latency_seconds" in metrics_text
        assert "outstanding_orders_total" in metrics_text
        assert "current_inventory" in metrics_text
        assert "current_pnl" in metrics_text

        # verify metrics have data
        assert (
            "engine_loops_total 1" in metrics_text
            or "engine_loops_total{} 1" in metrics_text
        )


@pytest.mark.asyncio
async def test_integration_with_live_engine():
    """integration test verifying metrics work with live engine components"""
    from live.engine import LiveEngine

    # create engine with metrics
    engine = LiveEngine(symbol="btcusdt")

    # verify metrics are initialized
    assert hasattr(engine, "metrics")
    assert engine.metrics.symbol == "btcusdt"

    # test metrics collection methods exist
    assert hasattr(engine.metrics, "record_engine_loop")
    assert hasattr(engine.metrics, "record_fill")
    assert hasattr(engine.metrics, "update_outstanding_orders")

    # cleanup
    await engine.metrics.close()
