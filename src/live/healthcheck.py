"""prometheus metrics endpoint for live trading system"""

import asyncio
from decimal import Decimal

import redis.asyncio as redis
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class HealthcheckMetrics:
    def __init__(
        self, redis_url: str = "redis://localhost:6379", symbol: str = "btcusdt"
    ):
        self.redis_url = redis_url
        self.symbol = symbol
        self.redis_client = None
        self._owns_redis_connection = True

        self.registry = CollectorRegistry()

        self.engine_loop_latency = Histogram(
            "engine_loop_latency_seconds",
            "Time spent processing each engine loop",
            registry=self.registry,
        )

        self.outstanding_orders = Gauge(
            "outstanding_orders_total",
            "Number of outstanding orders",
            ["side"],
            registry=self.registry,
        )

        self.current_inventory = Gauge(
            "current_inventory_btc",
            "Current inventory position in BTC",
            registry=self.registry,
        )

        self.current_pnl = Gauge(
            "current_pnl_usdt", "Current PnL in USDT", registry=self.registry
        )

        self.engine_loops_total = Counter(
            "engine_loops_total",
            "Total number of engine loops processed",
            registry=self.registry,
        )

        self.fills_total = Counter(
            "fills_total",
            "Total number of fills processed",
            ["side"],
            registry=self.registry,
        )

    async def update_outstanding_orders(
        self, bid_orders: int = 0, ask_orders: int = 0
    ) -> None:
        self.outstanding_orders.labels(side="buy").set(bid_orders)
        self.outstanding_orders.labels(side="sell").set(ask_orders)

    async def update_position_metrics(self) -> None:
        if not self.redis_client:
            self.redis_client = redis.from_url(self.redis_url)
            self._owns_redis_connection = True

        try:
            position_key = f"position:{self.symbol}"
            pnl_key = f"pnl:{self.symbol}"

            position_str = await self.redis_client.get(position_key)
            position = float(Decimal(position_str.decode())) if position_str else 0.0

            pnl_str = await self.redis_client.get(pnl_key)
            pnl = float(Decimal(pnl_str.decode())) if pnl_str else 0.0

            self.current_inventory.set(position)
            self.current_pnl.set(pnl)

        except Exception:
            pass

    def record_engine_loop(self, duration: float) -> None:
        self.engine_loop_latency.observe(duration)
        self.engine_loops_total.inc()

    def record_fill(self, side: str) -> None:
        self.fills_total.labels(side=side).inc()

    async def get_metrics(self) -> bytes:
        await self.update_position_metrics()
        return generate_latest(self.registry)

    async def close(self):
        if self.redis_client and self._owns_redis_connection:
            await self.redis_client.aclose()
            self.redis_client = None


class HealthcheckServer:
    def __init__(self, metrics: HealthcheckMetrics, port: int = 8000):
        self.metrics = metrics
        self.port = port
        self.server = None

    async def handle_metrics(self, request) -> tuple:
        metrics_data = await self.metrics.get_metrics()
        return (200, {"Content-Type": CONTENT_TYPE_LATEST}, metrics_data)

    async def handle_health(self, request) -> tuple:
        return (200, {"Content-Type": "application/json"}, b'{"status": "ok"}')

    async def start(self) -> None:
        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_get("/metrics", self._aiohttp_metrics_handler)
            app.router.add_get("/health", self._aiohttp_health_handler)

            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, "0.0.0.0", self.port)
            await site.start()
            self.server = runner

        except ImportError:
            import http.server
            import socketserver
            from threading import Thread

            class MetricsHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == "/metrics":
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            metrics_data = loop.run_until_complete(
                                self.server.metrics.get_metrics()
                            )
                            self.send_response(200)
                            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                            self.end_headers()
                            self.wfile.write(metrics_data)
                        finally:
                            loop.close()
                    elif self.path == "/health":
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(b'{"status": "ok"}')
                    else:
                        self.send_response(404)

            MetricsHandler.server = self
            httpd = socketserver.TCPServer(("", self.port), MetricsHandler)
            thread = Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.server = httpd

    async def _aiohttp_metrics_handler(self, request):
        from aiohttp import web

        metrics_data = await self.metrics.get_metrics()
        return web.Response(body=metrics_data, content_type=CONTENT_TYPE_LATEST)

    async def _aiohttp_health_handler(self, request):
        from aiohttp import web

        return web.json_response({"status": "ok"})

    async def stop(self) -> None:
        if self.server:
            if hasattr(self.server, "cleanup"):
                await self.server.cleanup()
            else:
                self.server.shutdown()


async def main():
    """example usage"""
    metrics = HealthcheckMetrics()
    server = HealthcheckServer(metrics)

    try:
        await server.start()
        print("metrics server running on :8000")
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("shutting down")
    finally:
        await server.stop()
        await metrics.close()


if __name__ == "__main__":
    asyncio.run(main())
