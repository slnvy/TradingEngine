#!/bin/bash

# Development environment setup script
set -e

echo "🔧 Setting up Market Maker development environment..."

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    echo "❌ Error: Please run this script from the Market_Maker project root"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | grep -o 'Python [0-9]\+\.[0-9]\+' | grep -o '[0-9]\+\.[0-9]\+')
REQUIRED_VERSION="3.11"

if [[ "$PYTHON_VERSION" != "$REQUIRED_VERSION"* ]]; then
    echo "❌ Error: Python $REQUIRED_VERSION is required, but you have Python $PYTHON_VERSION"
    echo "   Please install Python 3.11 or use pyenv to switch versions"
    echo "   With pyenv: pyenv install 3.11.13 && pyenv local 3.11.13"
    exit 1
fi

echo "✅ Python version check passed: $PYTHON_VERSION"

# Activate virtual environment
if [[ ! -d "venv" ]]; then
    echo "❌ Error: Virtual environment not found. Please create one first:"
    echo "   python -m venv venv"
    exit 1
fi

echo "🔍 Activating virtual environment..."
source venv/bin/activate

# Verify Python version in venv
VENV_PYTHON_VERSION=$(python --version 2>&1 | grep -o 'Python [0-9]\+\.[0-9]\+' | grep -o '[0-9]\+\.[0-9]\+')
if [[ "$VENV_PYTHON_VERSION" != "$REQUIRED_VERSION"* ]]; then
    echo "❌ Error: Virtual environment has Python $VENV_PYTHON_VERSION, but Python $REQUIRED_VERSION is required"
    echo "   Please recreate the virtual environment with Python 3.11"
    exit 1
fi

echo "✅ Virtual environment Python version: $VENV_PYTHON_VERSION"

# Install dependencies
echo "📦 Installing dependencies..."
make install

# Set up pre-commit hooks
echo "🪝 Setting up pre-commit hooks..."
pip install pre-commit
pre-commit install

# Run initial lint check
echo "🧹 Running lint check..."
make lint

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Always activate the virtual environment: source venv/bin/activate"
echo "  2. Before making changes, run: make lint"
echo "  3. Pre-commit hooks will automatically run on git commit"
echo "" 