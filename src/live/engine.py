"""live trading engine for market making"""

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Dict, Optional

import redis.asyncio as redis

from data_feed.schemas import DepthUpdate
from features.volatility import VolatilityCalculator
from live.binance_gateway import BinanceGateway
from live.healthcheck import HealthcheckMetrics, HealthcheckServer
from models.size_calculator import SizeConfig
from strategy.ev_maker import EVConfig, EVMaker

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LiveEngine:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        symbol: str = "btcusdt",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
    ):
        self.redis_url = redis_url
        self.redis_client = redis.from_url(redis_url)
        self.symbol = symbol.lower()
        self.stream_key = f"depth_updates:{self.symbol}"
        self.position_key = f"position:{self.symbol}"
        self.pnl_key = f"pnl:{self.symbol}"

        self.running = False
        self.current_inventory = Decimal("0")

        self.current_bid_order_id = None
        self.current_ask_order_id = None
        self.last_trade_id = None

        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        self.gateway = None

        self.volatility_calc = VolatilityCalculator(window_size=20)

        ev_config = EVConfig()
        size_config = SizeConfig()
        self.ev_maker = EVMaker(ev_config, size_config)

        self.metrics = HealthcheckMetrics(redis_url=redis_url)
        self.metrics_server = None

    async def start(self) -> None:
        """start the live engine"""
        logger.info("starting live engine")
        self.running = True

        self.metrics.redis_client = self.redis_client
        self.metrics._owns_redis_connection = False

        if self.api_key and self.api_secret:
            self.gateway = BinanceGateway(self.api_key, self.api_secret, self.testnet)
            logger.info("binance gateway initialized")
        else:
            logger.warning(
                "no binance credentials provided, running in simulation mode"
            )

        await self._initialize_redis_state()

        self.metrics_server = HealthcheckServer(self.metrics, port=8000)
        await self.metrics_server.start()
        logger.info("metrics server started on :8000")

        try:
            if self.gateway:
                async with self.gateway:
                    await self._run_loop()
            else:
                await self._run_loop()
        except KeyboardInterrupt:
            logger.info("received keyboard interrupt")
        except Exception as e:
            logger.error(f"error in live engine: {e}")
        finally:
            await self.stop()

    async def _run_loop(self) -> None:
        """main engine loop"""
        while self.running:
            messages = await self.redis_client.xread(
                {self.stream_key: "$"},
                count=1,
                block=100,
            )

            if not messages:
                continue

            stream_name, stream_messages = messages[0]

            for message_id, fields in stream_messages:
                await self._process_message(fields)

    async def stop(self) -> None:
        """stop the live engine"""
        logger.info("stopping live engine")
        self.running = False

        if self.metrics_server:
            await self.metrics_server.stop()

        if self.metrics:
            self.metrics.redis_client = None

        if self.redis_client:
            await self.redis_client.aclose()

    async def _initialize_redis_state(self) -> None:
        try:
            position_exists = await self.redis_client.exists(self.position_key)
            if not position_exists:
                await self.redis_client.set(self.position_key, "0")
                logger.info(f"initialized position key {self.position_key} to 0")

            pnl_exists = await self.redis_client.exists(self.pnl_key)
            if not pnl_exists:
                await self.redis_client.set(self.pnl_key, "0")
                logger.info(f"initialized pnl key {self.pnl_key} to 0")

            position_str = await self.redis_client.get(self.position_key)
            if position_str:
                self.current_inventory = Decimal(position_str.decode())
                logger.info(f"loaded current inventory: {self.current_inventory}")

        except Exception as e:
            logger.error(f"error initializing redis state: {e}")

    async def _process_message(self, fields: Dict) -> None:
        loop_start_time = time.time()

        try:
            message_data = json.loads(fields[b"data"].decode())
            depth_update = DepthUpdate(**message_data)

            bids = depth_update.b
            asks = depth_update.a

            if not bids or not asks:
                return

            best_bid = Decimal(bids[0][0])
            best_ask = Decimal(asks[0][0])
            mid_price = (best_bid + best_ask) / Decimal("2")

            volatility = self.volatility_calc.update(mid_price)

            bid_quote, ask_quote = self.ev_maker.quote_prices(
                mid_price=mid_price,
                volatility=Decimal(str(volatility)),
                bid_probability=Decimal("0.5"),
                ask_probability=Decimal("0.5"),
                inventory=self.current_inventory,
                best_bid=best_bid,
                best_ask=best_ask,
                bids=bids,
                asks=asks,
            )

            print(
                f"quote: bid={bid_quote.price}@{bid_quote.size} "
                f"ask={ask_quote.price}@{ask_quote.size} "
                f"mid={mid_price} spread={ask_quote.price - bid_quote.price}"
            )

            if self.gateway:
                await self._manage_orders(bid_quote, ask_quote)
                await self._check_for_fills()

            loop_duration = time.time() - loop_start_time
            self.metrics.record_engine_loop(loop_duration)

        except Exception as e:
            logger.error(f"error processing message: {e}")
            loop_duration = time.time() - loop_start_time
            self.metrics.record_engine_loop(loop_duration)

    async def _manage_orders(self, bid_quote, ask_quote) -> None:
        try:
            await self._cancel_existing_orders()

            symbol = self.symbol.upper()

            try:
                bid_result = await self.gateway.post_order(
                    symbol=symbol,
                    side="BUY",
                    order_type="LIMIT",
                    quantity=bid_quote.size,
                    price=bid_quote.price,
                    time_in_force="GTC",
                )
                self.current_bid_order_id = str(bid_result.get("orderId"))
                logger.info(f"placed bid order: {bid_result}")
            except Exception as e:
                logger.error(f"failed to place bid order: {e}")

            try:
                ask_result = await self.gateway.post_order(
                    symbol=symbol,
                    side="SELL",
                    order_type="LIMIT",
                    quantity=ask_quote.size,
                    price=ask_quote.price,
                    time_in_force="GTC",
                )
                self.current_ask_order_id = str(ask_result.get("orderId"))
                logger.info(f"placed ask order: {ask_result}")
            except Exception as e:
                logger.error(f"failed to place ask order: {e}")

            bid_count = 1 if self.current_bid_order_id else 0
            ask_count = 1 if self.current_ask_order_id else 0
            await self.metrics.update_outstanding_orders(bid_count, ask_count)

        except Exception as e:
            logger.error(f"error managing orders: {e}")

    async def _cancel_existing_orders(self) -> None:
        try:
            symbol = self.symbol.upper()

            if self.current_bid_order_id:
                try:
                    await self.gateway.cancel_order(
                        symbol, order_id=int(self.current_bid_order_id)
                    )
                    logger.info(f"canceled bid order: {self.current_bid_order_id}")
                except Exception as e:
                    logger.warning(f"failed to cancel bid order: {e}")
                finally:
                    self.current_bid_order_id = None

            if self.current_ask_order_id:
                try:
                    await self.gateway.cancel_order(
                        symbol, order_id=int(self.current_ask_order_id)
                    )
                    logger.info(f"canceled ask order: {self.current_ask_order_id}")
                except Exception as e:
                    logger.warning(f"failed to cancel ask order: {e}")
                finally:
                    self.current_ask_order_id = None

        except Exception as e:
            logger.error(f"error canceling orders: {e}")

    async def _check_for_fills(self) -> None:
        try:
            symbol = self.symbol.upper()
            trades = await self.gateway.get_account_trades(
                symbol=symbol,
                limit=10,
                from_id=self.last_trade_id,
            )

            if not trades:
                return

            for trade in trades:
                trade_id = int(trade["id"])

                if self.last_trade_id and trade_id <= self.last_trade_id:
                    continue

                await self._process_fill(trade)
                self.last_trade_id = trade_id

        except Exception as e:
            logger.error(f"error checking for fills: {e}")

    async def _process_fill(self, trade: Dict) -> None:
        try:
            side = trade["isBuyer"]
            price = Decimal(trade["price"])
            qty = Decimal(trade["qty"])
            commission = Decimal(trade["commission"])

            if side:
                position_change = qty
            else:
                position_change = -qty

            self.current_inventory += position_change

            pnl_change = -commission

            await self._update_redis_state(
                position_change, pnl_change, price, qty, side
            )

            fill_side = "buy" if side else "sell"
            self.metrics.record_fill(fill_side)

            logger.info(
                f"fill processed: side={'BUY' if side else 'SELL'} "
                f"price={price} qty={qty} new_inventory={self.current_inventory}"
            )

        except Exception as e:
            logger.error(f"error processing fill: {e}")

    async def _update_redis_state(
        self,
        position_change: Decimal,
        pnl_change: Decimal,
        price: Decimal,
        qty: Decimal,
        is_buyer: bool,
    ) -> None:
        try:
            position = float(self.current_inventory)
            await self.redis_client.set(self.position_key, str(position))

            current_pnl_str = await self.redis_client.get(self.pnl_key)
            current_pnl = (
                Decimal(current_pnl_str.decode()) if current_pnl_str else Decimal("0")
            )
            new_pnl = current_pnl + pnl_change
            await self.redis_client.set(self.pnl_key, str(new_pnl))

            logger.info(f"updated redis: position={position}, pnl={new_pnl}")

        except Exception as e:
            logger.error(f"error updating redis state: {e}")


async def main():
    """main function for testing"""
    engine = LiveEngine()
    await engine.start()


if __name__ == "__main__":
    asyncio.run(main())
