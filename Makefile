.PHONY: test lint clean backtest live install check-env setup-dev

install:
	pip install -e ".[dev]"

test:
	PYTHONPATH=src pytest tests/ -m "not skip and not backtest_regression"

lint:
	PYTHONPATH=src flake8 src/ tests/
	PYTHONPATH=src black --check src/ tests/
	PYTHONPATH=src isort --check-only src/ tests/

format:
	black src/ tests/
	isort src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name "*.egg" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".coverage" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +
	find . -type d -name "dist" -exec rm -r {} +
	find . -type d -name "build" -exec rm -r {} +

backtest:
	@echo "Running backtest for a single date (specify with: make backtest DATE=2023-01-01)"
	@if [ -z "$(DATE)" ]; then \
		echo "Example: make backtest DATE=2023-01-01"; \
		echo "Or run directly: python -m src.cli backtest --date 2023-01-01"; \
		python -m src.cli backtest --help; \
	else \
		python -m src.cli backtest --date $(DATE); \
	fi

live:
	@echo "Starting live trading engine in simulation mode"
	python -m src.cli live

check-env:
	@echo "Checking development environment..."
	@python -c "import sys; v=sys.version_info; assert v.major==3 and v.minor==11, f'Python 3.11 required, got {v.major}.{v.minor}'; print(f'✅ Python {v.major}.{v.minor}.{v.micro}')"
	@echo "✅ Environment check passed"

setup-dev:
	@bash scripts/setup-dev.sh 