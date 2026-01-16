#!/bin/bash

# Test runner script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "🧪 Running tests for Voice Sales Agent..."

# Parse arguments
COVERAGE=false
VERBOSE=false
TEST_PATH=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            TEST_PATH=$1
            shift
            ;;
    esac
done

# Activate virtual environment
if [ -f "$BACKEND_DIR/venv/bin/activate" ]; then
    source "$BACKEND_DIR/venv/bin/activate"
else
    echo "❌ Virtual environment not found. Run start-dev.sh first."
    exit 1
fi

cd "$BACKEND_DIR"

# Build pytest command
PYTEST_CMD="pytest"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing --cov-report=html"
fi

if [ -n "$TEST_PATH" ]; then
    PYTEST_CMD="$PYTEST_CMD $TEST_PATH"
else
    PYTEST_CMD="$PYTEST_CMD tests/"
fi

# Run tests
echo "Running: $PYTEST_CMD"
$PYTEST_CMD

if [ "$COVERAGE" = true ]; then
    echo "📊 Coverage report generated at: $BACKEND_DIR/htmlcov/index.html"
fi

echo "✅ Tests completed!"