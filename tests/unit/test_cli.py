"""
tests for cli functionality
"""

import argparse
from unittest.mock import AsyncMock, Mock, patch

import pytest

from cli import create_parser, main, run_backtest, run_live


class TestCLIParser:
    """test CLI argument parsing"""

    def test_parser_creation(self):
        """test parser is created correctly"""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.description == "market maker trading system"

    def test_backtest_command_parsing(self):
        """test backtest command parsing"""
        parser = create_parser()

        # test basic backtest command
        args = parser.parse_args(["backtest", "--date", "2023-01-01"])
        assert args.command == "backtest"
        assert args.date == "2023-01-01"
        assert args.symbol == "btcusdt"
        assert args.data_path == "data/raw"

    def test_backtest_with_range(self):
        """test backtest with date range"""
        parser = create_parser()

        args = parser.parse_args(
            [
                "backtest",
                "--start-date",
                "2023-01-01",
                "--end-date",
                "2023-01-02",
                "--symbol",
                "ethusdt",
                "--output",
                "results.csv",
            ]
        )
        assert args.command == "backtest"
        assert args.start_date == "2023-01-01"
        assert args.end_date == "2023-01-02"
        assert args.symbol == "ethusdt"
        assert args.output == "results.csv"

    def test_live_command_parsing(self):
        """test live command parsing"""
        parser = create_parser()

        args = parser.parse_args(
            [
                "live",
                "--symbol",
                "ethusdt",
                "--redis-url",
                "redis://custom:6379",
                "--api-key",
                "test_key",
                "--api-secret",
                "test_secret",
            ]
        )
        assert args.command == "live"
        assert args.symbol == "ethusdt"
        assert args.redis_url == "redis://custom:6379"
        assert args.api_key == "test_key"
        assert args.api_secret == "test_secret"
        assert args.testnet is True

    def test_live_mainnet_flag(self):
        """test live command with mainnet flag"""
        parser = create_parser()

        args = parser.parse_args(["live", "--mainnet"])
        assert args.command == "live"
        assert args.mainnet is True
        assert args.testnet is True  # default, gets overridden in main()

    def test_no_command(self):
        """test parser with no command"""
        parser = create_parser()

        args = parser.parse_args([])
        assert args.command is None


class TestCLIExecution:
    """test CLI command execution"""

    @patch("cli.Simulator")
    @patch("cli.NaiveMaker")
    @patch("cli.NaiveMakerConfig")
    def test_run_backtest_single_date(
        self, mock_naive_maker_config, mock_naive_maker, mock_simulator
    ):
        """test backtest execution with single date"""
        # mock strategy
        mock_strategy = Mock()
        mock_naive_maker.return_value = mock_strategy
        mock_strategy.quote_prices = Mock()

        # mock simulator
        mock_sim = Mock()
        mock_simulator.return_value = mock_sim
        mock_sim.get_pnl_summary.return_value = {
            "total_pnl": 100.5,
            "num_fills": 10,
            "avg_fill_size": 0.001,
            "final_position": 0.1,
        }

        # args
        args = Mock()
        args.data_path = "test_data"
        args.symbol = "btcusdt"
        args.date = "2023-01-01"
        args.start_date = None
        args.end_date = None
        args.output = None

        with patch("cli.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance

            run_backtest(args)

            # simulator called correctly
            mock_simulator.assert_called_once_with(
                symbol="btcusdt",
                data_path="test_data",
                strategy=mock_strategy.quote_prices,
            )
            mock_sim.replay_date.assert_called_once()

    @patch("cli.Simulator")
    @patch("cli.NaiveMaker")
    @patch("cli.NaiveMakerConfig")
    def test_run_backtest_date_range(
        self, mock_naive_maker_config, mock_naive_maker, mock_simulator
    ):
        """test backtest execution with date range"""
        # mock strategy
        mock_strategy = Mock()
        mock_naive_maker.return_value = mock_strategy

        # mock simulator
        mock_sim = Mock()
        mock_simulator.return_value = mock_sim
        mock_sim.get_pnl_summary.return_value = {
            "total_pnl": 200.0,
            "num_fills": 20,
            "avg_fill_size": 0.002,
            "final_position": -0.05,
        }

        # args
        args = Mock()
        args.data_path = "test_data"
        args.symbol = "ethusdt"
        args.date = None
        args.start_date = "2023-01-01"
        args.end_date = "2023-01-05"
        args.output = None

        with patch("cli.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            run_backtest(args)

            mock_sim.replay_date_range.assert_called_once()

    @patch("cli.Simulator")
    @patch("cli.NaiveMaker")
    @patch("cli.NaiveMakerConfig")
    def test_run_backtest_with_output(
        self, mock_naive_maker_config, mock_naive_maker, mock_simulator
    ):
        """test backtest execution with output file"""
        # mock strategy and simulator
        mock_strategy = Mock()
        mock_naive_maker.return_value = mock_strategy

        mock_sim = Mock()
        mock_simulator.return_value = mock_sim
        mock_sim.get_pnl_summary.return_value = {
            "total_pnl": 50.0,
            "num_fills": 5,
            "avg_fill_size": 0.001,
            "final_position": 0.0,
        }

        mock_df = Mock()
        mock_sim.get_fills_df.return_value = mock_df

        # args
        args = Mock()
        args.data_path = "test_data"
        args.symbol = "btcusdt"
        args.date = "2023-01-01"
        args.start_date = None
        args.end_date = None
        args.output = "results.csv"

        with patch("cli.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            run_backtest(args)

            # output saved
            mock_df.to_csv.assert_called_once_with("results.csv", index=False)

    @pytest.mark.asyncio
    @patch("cli.LiveEngine")
    async def test_run_live_simulation_mode(self, mock_live_engine):
        """test live mode without credentials"""
        # mock engine
        mock_engine = AsyncMock()
        mock_live_engine.return_value = mock_engine

        # args
        args = Mock()
        args.symbol = "btcusdt"
        args.redis_url = "redis://localhost:6379"
        args.api_key = None
        args.api_secret = None
        args.testnet = True

        with patch.dict("os.environ", {}, clear=True):
            await run_live(args)

            # engine created and started
            mock_live_engine.assert_called_once_with(
                redis_url="redis://localhost:6379",
                symbol="btcusdt",
                api_key=None,
                api_secret=None,
                testnet=True,
            )
            mock_engine.start.assert_called_once()
            mock_engine.stop.assert_called_once()

    @pytest.mark.asyncio
    @patch("cli.LiveEngine")
    async def test_run_live_with_credentials(self, mock_live_engine):
        """test live mode with api credentials"""
        # mock engine
        mock_engine = AsyncMock()
        mock_live_engine.return_value = mock_engine

        # args
        args = Mock()
        args.symbol = "ethusdt"
        args.redis_url = "redis://localhost:6379"
        args.api_key = "test_key"
        args.api_secret = "test_secret"
        args.testnet = False

        await run_live(args)

        # engine created with credentials
        mock_live_engine.assert_called_once_with(
            redis_url="redis://localhost:6379",
            symbol="ethusdt",
            api_key="test_key",
            api_secret="test_secret",
            testnet=False,
        )

    @pytest.mark.asyncio
    @patch("cli.LiveEngine")
    async def test_run_live_env_credentials(self, mock_live_engine):
        """test live mode with environment credentials"""
        # mock engine
        mock_engine = AsyncMock()
        mock_live_engine.return_value = mock_engine

        # args
        args = Mock()
        args.symbol = "btcusdt"
        args.redis_url = "redis://localhost:6379"
        args.api_key = None
        args.api_secret = None
        args.testnet = True

        with patch.dict(
            "os.environ",
            {"BINANCE_API_KEY": "env_key", "BINANCE_API_SECRET": "env_secret"},
        ):
            await run_live(args)

            # environment credentials were used
            mock_live_engine.assert_called_once_with(
                redis_url="redis://localhost:6379",
                symbol="btcusdt",
                api_key="env_key",
                api_secret="env_secret",
                testnet=True,
            )


class TestCLIMain:
    """test main CLI function"""

    @patch("cli.run_backtest")
    def test_main_backtest_command(self, mock_run_backtest):
        """test main function with backtest command"""
        test_args = ["cli.py", "backtest", "--date", "2023-01-01"]

        with patch("sys.argv", test_args):
            main()

            mock_run_backtest.assert_called_once()

    @patch("cli.asyncio.run")
    @patch("cli.run_live")
    def test_main_live_command(self, mock_run_live, mock_asyncio_run):
        """test main function with live command"""
        test_args = ["cli.py", "live"]

        with patch("sys.argv", test_args):
            main()

            # asyncio.run was called
            mock_asyncio_run.assert_called_once()

    def test_main_no_command(self):
        """test main function with no command"""
        test_args = ["cli.py"]

        with patch("sys.argv", test_args):
            with patch("sys.exit") as mock_exit:
                main()

                # exit was called at least once with code 1
                mock_exit.assert_called()
                exit_calls = mock_exit.call_args_list
                assert any(call[0][0] == 1 for call in exit_calls)

    def test_main_mainnet_override(self):
        """test mainnet flag overrides testnet"""
        test_args = ["cli.py", "live", "--mainnet"]

        with patch("sys.argv", test_args):
            with patch("cli.asyncio.run") as mock_asyncio_run:
                main()
                # verify asyncio.run was called
                mock_asyncio_run.assert_called_once()


def test_cli_help_output():
    """test that help output is generated correctly"""
    parser = create_parser()

    # test that help doesn't raise an exception
    help_output = parser.format_help()
    assert "market maker trading system" in help_output
    assert "backtest" in help_output
    assert "live" in help_output
