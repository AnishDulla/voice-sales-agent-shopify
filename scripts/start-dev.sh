#!/bin/bash

# Development startup script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "🚀 Starting Voice Sales Agent in development mode..."

# Check for .env file
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo "📝 Please edit backend/.env with your API keys"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
required_version="3.9"

# Convert versions to comparable format (e.g., 3.9 -> 309, 3.11 -> 311)
python_ver_num=$(echo $python_version | awk -F. '{printf "%d%02d", $1, $2}')
required_ver_num=$(echo $required_version | awk -F. '{printf "%d%02d", $1, $2}')

if [ "$python_ver_num" -lt "$required_ver_num" ]; then
    echo "❌ Python $required_version or higher is required (found $python_version)"
    echo "💡 Try using a newer Python version or update your Python installation"
    echo "💡 You can also modify the requirements in pyproject.toml if you want to use Python 3.9+"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo "📦 Creating virtual environment..."
    cd "$BACKEND_DIR"
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source "$BACKEND_DIR/venv/bin/activate"

# Install dependencies
echo "📚 Installing dependencies..."
cd "$BACKEND_DIR"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Run database migrations (if any)
# echo "🗄️  Running migrations..."
# alembic upgrade head

# Start the application
echo "✅ Starting API server..."
cd "$BACKEND_DIR"
python -m src.main --mode api