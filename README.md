# Voice Sales Agent for Shopify

A production-ready voice-enabled sales assistant for Shopify stores, built with LangGraph, LiveKit, and the Shopify Admin API.

## 🚀 Features

- **🎤 Voice Interaction**: Natural conversation via real-time STT → LLM → TTS pipeline
- **🛍️ Product Discovery**: Answer questions about products, inventory, and specifications  
- **🔧 Extensible Architecture**: Tool-based design for easy feature additions
- **🏗️ Production Ready**: Proper error handling, logging, and monitoring
- **🧪 Testing Interface**: HTML frontend for voice testing and debugging

## 📋 Prerequisites

- Python 3.9+ 
- OpenAI API key
- Shopify store with Admin API access
- LiveKit account (for voice features)

## ⚡ Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/AnishDulla/voice-sales-agent-shopify.git
cd voice-sales-agent-shopify
```

### 2. Environment Setup
```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit with your actual API keys
nano backend/.env
```

Required environment variables:
- `SHOPIFY_STORE_URL`: Your Shopify store URL
- `SHOPIFY_ACCESS_TOKEN`: Shopify Admin API access token
- `OPENAI_API_KEY`: OpenAI API key
- `LIVEKIT_URL`: LiveKit WebSocket URL
- `LIVEKIT_API_KEY`: LiveKit API key
- `LIVEKIT_API_SECRET`: LiveKit API secret

### 3. Run Application
```bash
# Start backend server
./scripts/start-dev.sh

# Open frontend in browser
open frontend/index.html
```

## 🧪 Testing the Voice Agent

1. **Start Backend**: Run `./scripts/start-dev.sh`
2. **Open Frontend**: Double-click `frontend/index.html`
3. **Connect**: Click "🔌 Connect" button
4. **Test Voice**: Click "🎤 Start Voice" and speak
5. **Test Text**: Type in the input field

### Example Queries
- *"Show me your running shoes"*
- *"What products do you have under $150?"*
- *"Tell me about the Nike Air Zoom Pegasus"*
- *"Is size 10 available in black?"*

## Architecture

### Core Components

- **Domains**: Pure business logic (Shopify, Voice, Cart, etc.)
- **Tools**: Agent capabilities exposed as tools
- **Agent**: LangGraph-based orchestration
- **Infrastructure**: LiveKit, FastAPI, persistence

### Key Principles

1. **Tool-First**: Agent only interacts through tools
2. **Domain-Driven**: Clear boundaries between business logic
3. **Test-Driven**: Comprehensive test coverage
4. **Extensible**: Easy to add new capabilities

## Configuration

Required environment variables:

```env
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your-access-token
OPENAI_API_KEY=your-openai-key
LIVEKIT_URL=your-livekit-url
LIVEKIT_API_KEY=your-livekit-key
LIVEKIT_API_SECRET=your-livekit-secret
```

## Development

### Adding New Tools

1. Create tool in `backend/src/orchestration/tools/`
2. Register in tool registry
3. Add tests in `backend/tests/unit/orchestration/`
4. Update agent prompts if needed

### Testing

```bash
# Run all tests
./scripts/test.sh

# Run specific test suite
pytest backend/tests/unit/

# Run with coverage
pytest --cov=backend/src backend/tests/
```

## Deployment

See [docs/deployment.md](docs/deployment.md) for production deployment guide.

## License

Proprietary