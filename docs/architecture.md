Market-Making System Architecture

Technical documentation for the Market_Maker system.

⸻

## Project Structure

```
Market_Maker/
├── README.md
├── Makefile
├── pyproject.toml
├── setup.py
├── pytest.ini
├── .gitignore
├── tasks.md                     # development task list
├── docs/
│   └── architecture.md          # this document
├── docker/
│   ├── docker-compose.yml       # monitoring stack
│   ├── prometheus.yml           # prometheus configuration
│   ├── README.md                # docker setup guide
│   └── grafana/
│       ├── provisioning/
│       │   ├── dashboards/default.yml
│       │   └── datasources/prometheus.yml
│       └── dashboards/
│           └── market-maker.json
├── data/
│   ├── raw/                     # L2 tick data (parquet)
│   ├── processed/               # backtest results, features
│   └── models/                  # trained models
├── src/
│   ├── __init__.py
│   ├── cli.py                   # command line interface
│   ├── common/                  # shared utilities
│   ├── data_feed/               # market data ingestion
│   │   ├── binance_ws.py        # websocket client
│   │   ├── recorder.py          # data recording
│   │   ├── parquet_writer.py    # storage backend
│   │   └── schemas.py           # data schemas
│   ├── storage/                 # persistence layer
│   ├── lob/                     # limit order book
│   │   ├── order_book.py        # python implementation
│   │   ├── match_engine.cpp     # c++ optimized engine
│   │   └── *.so                 # compiled binaries
│   ├── features/                # feature engineering
│   │   ├── imbalance.py         # order book imbalance
│   │   ├── volatility.py        # volatility calculations
│   │   └── micro_price.py       # microprice estimation
│   ├── models/                  # predictive models
│   │   ├── fill_prob.py         # fill probability model
│   │   ├── inventory_skew.py    # inventory management
│   │   └── size_calculator.py   # position sizing
│   ├── strategy/                # trading strategies
│   │   ├── naive_maker.py       # fixed spread strategy
│   │   └── ev_maker.py          # expected value strategy
│   ├── backtest/                # backtesting framework
│   │   └── simulator.py         # event-driven simulator
│   ├── live/                    # live trading engine
│   │   ├── engine.py            # main trading loop
│   │   ├── binance_gateway.py   # exchange connectivity
│   │   └── healthcheck.py       # metrics endpoint
│   ├── api/                     # rest api (unused)
│   └── market_maker/            # legacy structure
├── scripts/
│   ├── setup-dev.sh             # development setup
│   ├── start_dashboard.sh       # monitoring startup
│   ├── generate_test_data.py    # test data generation
│   ├── inspect_parquet.py       # data inspection
│   ├── test_recorder.py         # manual testing
│   └── test_binance_ws.py       # websocket testing
├── tests/
│   ├── unit/                    # unit tests
│   ├── integration/             # integration tests
│   ├── backtest/                # backtesting tests
│   └── data/                    # test fixtures
├── test_data/                   # generated test data
├── venv/                        # python environment
└── .github/
    └── workflows/ci.yml         # continuous integration
```

⸻

## Component Overview

### Core Components

**CLI Interface (`src/cli.py`)**
- Main entry point for backtest and live trading modes
- Argument parsing and configuration management
- Environment variable support for credentials

**Data Ingestion (`src/data_feed/`)**
- `binance_ws.py`: websocket client for L2 orderbook data
- `recorder.py`: normalizes and persists market data
- `parquet_writer.py`: columnar storage for tick data
- `schemas.py`: data validation and normalization

**Order Book Engine (`src/lob/`)**
- `order_book.py`: python limit order book implementation
- `match_engine.cpp`: optimized c++ matching engine
- 10x+ performance improvement for backtesting

**Feature Engineering (`src/features/`)**
- `imbalance.py`: multi-level orderbook imbalance calculation
- `volatility.py`: rolling window volatility estimation
- `micro_price.py`: volume-weighted fair value calculation

**Predictive Models (`src/models/`)**
- `fill_prob.py`: logistic regression for fill probability
- `inventory_skew.py`: inventory-based quote adjustment
- `size_calculator.py`: optimal position sizing

**Trading Strategies (`src/strategy/`)**
- `naive_maker.py`: baseline fixed-spread market making
- `ev_maker.py`: expected value maximizing strategy

**Backtesting (`src/backtest/`)**
- `simulator.py`: event-driven backtesting engine
- historical tick data replay through LOB engine
- strategy performance evaluation

**Live Trading (`src/live/`)**
- `engine.py`: main async trading loop
- `binance_gateway.py`: REST API client for order management
- `healthcheck.py`: prometheus metrics exposure

**Monitoring (`docker/`)**
- prometheus + grafana stack for live observability
- real-time P&L, inventory, and performance metrics
- automated dashboard provisioning

### Development Tools

**Scripts**
- `setup-dev.sh`: development environment initialization
- `start_dashboard.sh`: monitoring stack startup
- various testing and inspection utilities

**Testing**
- comprehensive unit test coverage
- integration tests for data flow
- backtesting validation tests
- continuous integration via github actions

⸻

## Data Flow Architecture

### State Management

| Component | Storage | Purpose |
|-----------|---------|---------|
| Live orderbook | Redis stream | real-time quote calculation |
| Position tracking | Redis keys | inventory management |
| P&L tracking | Redis keys | performance monitoring |
| Order management | Redis hash | open order tracking |
| Historical data | Parquet files | backtesting and training |
| Model artifacts | Pickle files | strategy deployment |
| System metrics | Prometheus | operational monitoring |

### Processing Flow

**Data Ingestion**
1. binance websocket connection established
2. L2 orderbook updates received and normalized
3. concurrent writes to redis stream and parquet storage

**Live Trading**
1. trading engine subscribes to redis tick stream
2. real-time feature calculation from orderbook updates
3. model inference for fill probability and sizing
4. strategy generates optimal bid/ask quotes
5. order lifecycle management via REST API
6. position and P&L updates on fills
7. metrics exposure for monitoring

**Backtesting**
1. parquet tick data loaded for specified date range
2. historical orderbook reconstruction via c++ engine
3. strategy execution against historical data
4. performance metrics calculation and storage

**Monitoring**
1. live metrics exposed on port 8000
2. prometheus scraping at 5-second intervals
3. grafana dashboard visualization
4. real-time system health monitoring

⸻

## Deployment

### Command Line Usage

```bash
# backtesting
python -m src.cli backtest --start-date 2024-01-01 --symbol BTCUSDT

# live trading
python -m src.cli live --api-key <key> --api-secret <secret>

# monitoring
./scripts/start_dashboard.sh
```

### Requirements

- python 3.11+
- redis server
- docker + docker-compose (monitoring)
- binance API credentials

### Performance Characteristics

- sub-millisecond quote generation
- c++ optimized backtesting engine
- redis-based low-latency state management
- real-time risk controls and monitoring

⸻

## System Capabilities

The system provides:

- Real-time Binance L2 data ingestion
- High-performance c++ backtesting engine
- Machine learning driven fill probability modeling
- Inventory-aware risk management
- Live paper trading with testnet support
- Complete observability via grafana dashboards
- Command line interface for operations

The architecture supports professional market making operations with institutional-grade performance and monitoring capabilities.