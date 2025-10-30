"""
command-line interface for market maker

this module provides CLI commands for:
- backtest: run historical backtesting
- live: run live trading engine

usage:
    python -m src.cli backtest [options]
    python -m src.cli live [options]
"""

import argparse
import asyncio
import datetime
import logging
import os
import sys
from pathlib import Path

from backtest.simulator import Simulator
from live.engine import LiveEngine
from strategy.naive_maker import NaiveMaker, NaiveMakerConfig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_backtest(args) -> None:
    """run backtest mode

    Args:
        args: parsed command line arguments
    """
    logger.info("starting backtest mode")

    data_path = Path(args.data_path)
    if not data_path.exists():
        logger.error(f"data path does not exist: {data_path}")
        sys.exit(1)

    # strategy instance
    config = NaiveMakerConfig()
    naive_maker = NaiveMaker(config)

    # configure simulator
    simulator = Simulator(
        symbol=args.symbol,
        data_path=args.data_path,
        strategy=naive_maker.quote_prices,
    )

    try:
        if args.date:
            # run single date
            date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
            logger.info(f"running backtest for {date}")
            simulator.replay_date(date)
        else:
            # run date range
            start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
            logger.info(f"running backtest from {start_date} to {end_date}")
            simulator.replay_date_range(start_date, end_date)

        # print results
        pnl_summary = simulator.get_pnl_summary()
        logger.info("backtest completed successfully")
        logger.info(f"total pnl: {pnl_summary['total_pnl']:.4f}")
        logger.info(f"total fills: {pnl_summary['num_fills']}")
        logger.info(f"average fill size: {pnl_summary['avg_fill_size']:.6f}")
        logger.info(f"final position: {pnl_summary['final_position']:.6f}")

        # save results if requested
        if args.output:
            fills_df = simulator.get_fills_df()
            fills_df.to_csv(args.output, index=False)
            logger.info(f"results saved to {args.output}")

    except Exception as e:
        logger.error(f"backtest failed: {e}")
        sys.exit(1)


async def run_live(args) -> None:
    """run live trading mode

    Args:
        args: parsed command line arguments
    """
    logger.info("starting live trading mode")

    # get api credentials
    api_key = args.api_key or os.getenv("BINANCE_API_KEY")
    api_secret = args.api_secret or os.getenv("BINANCE_API_SECRET")

    if not api_key or not api_secret:
        logger.warning("no api credentials provided, running in simulation mode")
        api_key = None
        api_secret = None

    # configure live engine
    engine = LiveEngine(
        redis_url=args.redis_url,
        symbol=args.symbol,
        api_key=api_key,
        api_secret=api_secret,
        testnet=args.testnet,
    )

    try:
        logger.info(f"starting live engine for {args.symbol}")
        if api_key:
            logger.info("trading mode: live orders")
        else:
            logger.info("trading mode: simulation only")

        await engine.start()
    except KeyboardInterrupt:
        logger.info("received interrupt signal")
    except Exception as e:
        logger.error(f"live engine failed: {e}")
        sys.exit(1)
    finally:
        await engine.stop()
        logger.info("live engine stopped")


def create_parser() -> argparse.ArgumentParser:
    """create argument parser for CLI

    Returns:
        configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="market maker trading system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="available commands")

    # backtest command
    backtest_parser = subparsers.add_parser(
        "backtest",
        help="run historical backtesting",
    )
    backtest_parser.add_argument(
        "--symbol",
        type=str,
        default="btcusdt",
        help="trading pair symbol (default: btcusdt)",
    )
    backtest_parser.add_argument(
        "--data-path",
        type=str,
        default="data/raw",
        help="path to historical data files (default: data/raw)",
    )
    backtest_parser.add_argument(
        "--date",
        type=str,
        help="single date to backtest (YYYY-MM-DD)",
    )
    backtest_parser.add_argument(
        "--start-date",
        type=str,
        help="start date for backtest range (YYYY-MM-DD)",
    )
    backtest_parser.add_argument(
        "--end-date",
        type=str,
        help="end date for backtest range (YYYY-MM-DD)",
    )
    backtest_parser.add_argument(
        "--output",
        type=str,
        help="output file for results (csv format)",
    )

    # live command
    live_parser = subparsers.add_parser(
        "live",
        help="run live trading engine",
    )
    live_parser.add_argument(
        "--symbol",
        type=str,
        default="btcusdt",
        help="trading pair symbol (default: btcusdt)",
    )
    live_parser.add_argument(
        "--redis-url",
        type=str,
        default="redis://localhost:6379",
        help="redis connection url (default: redis://localhost:6379)",
    )
    live_parser.add_argument(
        "--api-key",
        type=str,
        help="binance api key (or set BINANCE_API_KEY env var)",
    )
    live_parser.add_argument(
        "--api-secret",
        type=str,
        help="binance api secret (or set BINANCE_API_SECRET env var)",
    )
    live_parser.add_argument(
        "--testnet",
        action="store_true",
        default=True,
        help="use binance testnet (default: true)",
    )
    live_parser.add_argument(
        "--mainnet",
        action="store_true",
        help="use binance mainnet (overrides --testnet)",
    )

    return parser


def main() -> None:
    """main CLI entry point"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # handle mainnet override
    if hasattr(args, "mainnet") and args.mainnet:
        args.testnet = False

    # validate backtest arguments
    if args.command == "backtest":
        if not args.date and not (args.start_date and args.end_date):
            logger.error(
                "must specify either --date or both --start-date and --end-date"
            )
            sys.exit(1)
        if args.date and (args.start_date or args.end_date):
            logger.error("cannot specify both --date and date range")
            sys.exit(1)

    try:
        if args.command == "backtest":
            run_backtest(args)
        elif args.command == "live":
            asyncio.run(run_live(args))
        else:
            logger.error(f"unknown command: {args.command}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
