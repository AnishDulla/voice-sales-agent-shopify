#!/bin/bash

# Development startup script with ngrok tunnel

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "🚀 Starting Voice Sales Agent with ngrok tunnel..."

# Check for .env file
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env" 2>/dev/null || echo "No .env.example found"
    echo "📝 Please edit backend/.env with your API keys"
    exit 1
fi

# Check for ngrok
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok not found. Please install it first:"
    echo "   brew install ngrok    (on macOS)"
    echo "   or download from https://ngrok.com"
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

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    
    # Kill backend if running
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        echo "✅ Stopped backend"
    fi
    
    # Kill ngrok if running
    if [ ! -z "$NGROK_PID" ]; then
        kill $NGROK_PID 2>/dev/null || true
        echo "✅ Stopped ngrok"
    fi
    
    exit 0
}

# Set up cleanup on script exit
trap cleanup EXIT INT TERM

# Start the backend
echo "🔧 Starting backend server..."
cd "$BACKEND_DIR"
export PYTHONPATH="$BACKEND_DIR/src:$PYTHONPATH"
python src/main.py &
BACKEND_PID=$!

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo "✅ Backend is running"
        break
    fi
    sleep 1
done

# Start ngrok tunnel
echo "🌐 Starting ngrok tunnel..."
ngrok http 8000 --log=stdout &
NGROK_PID=$!

# Wait for ngrok to establish tunnel
sleep 3

# Get the public URL
echo ""
echo "📡 Getting public URL..."
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for tunnel in data.get('tunnels', []):
        if tunnel.get('proto') == 'https':
            print(tunnel['public_url'])
            break
except:
    pass
")

if [ -z "$NGROK_URL" ]; then
    echo "⚠️  Could not get ngrok URL. Check http://localhost:4040 manually"
else
    echo ""
    echo "✅ BACKEND IS READY!"
    echo ""
    echo "🔗 LOCAL URL:"
    echo "   http://localhost:8000"
    echo ""
    echo "🌐 PUBLIC URL (via ngrok):"
    echo "   $NGROK_URL"
    echo ""
    echo "🎯 WEBHOOK URL FOR RETELL AI:"
    echo "   $NGROK_URL/api/voice/retell/webhook"
    echo ""
fi

echo "🛑 Press Ctrl+C to stop both services"
echo ""

# Keep script running
wait $BACKEND_PID