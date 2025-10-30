# Market Maker MVP

A high-frequency market making system for cryptocurrency markets, focusing on Binance BTCUSDT pair.

## Features

- Real-time market data ingestion from Binance WebSocket API
- Fast limit order book (LOB) engine with C++ matching core
- Advanced microstructure feature generation
- Expected value (EV) based quoting with fill probability modeling
- Inventory-aware risk management
- Live trading engine with paper trading support
- Comprehensive backtesting framework

## Requirements

- Python 3.11
- Redis (for real-time state management)

## Project Structure

```
Market_Maker/
├── src/                      # Source code
│   ├── cli.py               # Command line interface
│   ├── common/              # Shared utilities
│   ├── data_feed/           # Market data ingestion
│   ├── lob/                 # Limit Order Book engine
│   ├── features/            # Feature generation
│   ├── models/              # ML models
│   ├── strategy/            # Trading strategies
│   ├── backtest/            # Backtesting engine
│   └── live/                # Live trading
├── tests/                   # Test suite
├── data/                    # Data storage
├── scripts/                 # Helper scripts
├── docker/                  # Monitoring stack
└── docs/                    # Documentation
```

## Setup

1. Create and activate virtual environment:
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
# Install core dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

3. Configure environment:
- Copy `configs/env.dev.yaml.example` to `configs/env.dev.yaml`
- Add your Binance API keys

4. Run tests:
```bash
make test
```

## Usage

### Backtesting
```bash
python -m src.cli backtest --start-date 2024-01-01 --symbol BTCUSDT
```

### Live Trading
```bash
python -m src.cli live --api-key <key> --api-secret <secret>
```

## Development

- Follow PEP 8 style guide
- Write unit tests for new features
- Run `make lint` before committing

## Development Setup

**Important**: This project requires Python 3.11. Using a different Python version will cause CI failures due to formatting differences.

### Quick Start

1. **Ensure Python 3.11 is installed**
   ```bash
   python --version  # Should show Python 3.11.x
   ```

2. **Activate the virtual environment**
   ```bash
   source venv/bin/activate
   ```

3. **Verify you're using the correct Python version**
   ```bash
   python --version  # Should show Python 3.11.x
   ```

4. **Install dependencies**
   ```bash
   make install
   ```

5. **Set up pre-commit hooks (recommended)**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Before Making Changes

Always ensure you're using the project's virtual environment:
```bash
source venv/bin/activate
python --version  # Verify Python 3.11.x
make lint         # Run linting checks
```

### Common Issues

- **CI linting failures**: Usually caused by using the wrong Python version locally
- **Solution**: Always use `source venv/bin/activate` before development

## License

MIT 