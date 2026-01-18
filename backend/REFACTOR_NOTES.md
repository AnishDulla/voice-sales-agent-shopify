# Refactoring Notes - Voice Commerce Backend

## Overview
This backend has been refactored from a LangChain/LangGraph/LiveKit architecture to a clean domain-driven design with Retell AI integration.

## What Was Archived

### Archived Components (moved to `src/archive/`)
- **LangChain/LangGraph orchestration**: Old agent graph and chain logic
- **LiveKit infrastructure**: WebSocket handlers, voice pipeline
- **Custom STT/TTS**: Whisper transcription, Cartesia synthesis
- **Conversation domain**: Multi-turn conversation management
- **Old pipeline code**: Audio processing pipeline

### Why Archived
- **Retell AI handles**: Voice recognition, synthesis, LLM orchestration, conversation flow
- **Simplified architecture**: Pure HTTP API instead of WebSocket complexity
- **Reduced dependencies**: No need for heavy ML libraries
- **Better scalability**: Offload voice processing to Retell's infrastructure

## Current Architecture

### Domain Structure
```
src/
├── domains/
│   ├── shopify/        # E-commerce business logic
│   │   ├── services/    # Products, inventory, carts
│   │   └── routes.py    # HTTP endpoints
│   └── voice/           # Voice agent integration
│       ├── agent/       # Tool execution handler
│       ├── tools/       # Tool registry for Retell
│       └── routes.py    # Webhook endpoints
├── integrations/
│   ├── shopify/         # Shopify API client
│   └── retell/          # Retell AI client
├── app.py              # FastAPI application
└── config.py           # Settings management
```

### Key Changes
1. **WebSocket → HTTP**: All voice handling through Retell webhooks
2. **LangGraph → Direct Tools**: Simple tool execution without graph complexity
3. **LiveKit → Retell**: Voice infrastructure fully managed by Retell
4. **Complex Pipeline → Simple Handler**: Clean tool execution pattern

## How to Restore Archived Code

If you need to restore the old LangChain/LiveKit implementation:

```bash
# View archived files
ls -la backend/src/archive/

# Copy specific files back
cp backend/src/archive/orchestration/agent/graph.py backend/src/

# Or restore entire directories
cp -r backend/src/archive/infrastructure backend/src/
```

## Testing the New System

### Local Development
```bash
# Basic startup
./scripts/start-dev.sh

# With ngrok tunnel for webhooks
./scripts/start-dev-with-tunnel.sh
```

### Test Interfaces
- **API Tester**: `frontend/api-tester.html` - Test all HTTP endpoints
- **Voice Interface**: `frontend/retell-voice.html` - Test voice commands

### Retell AI Setup
1. Get webhook URL from ngrok: `https://xxxxx.ngrok.io/api/voice/retell/webhook`
2. Create agent at retellai.com with this webhook
3. Add `RETELL_API_KEY` to `.env`
4. Test voice commands through Retell

## Dependencies Removed

### No Longer Needed
- langchain, langchain-community
- langgraph
- livekit, livekit-agents
- openai-whisper
- cartesia
- pyaudio, sounddevice
- Most async streaming libraries

### Still Required
- fastapi, uvicorn (API server)
- pydantic (data validation)
- httpx (HTTP client)
- shopifyapi (e-commerce)

## Risks and TODOs

### Current Limitations
- ❗ Cart state is in-memory (use Redis in production)
- ❗ No authentication on endpoints (add API keys)
- ❗ Retell webhook not validated (add signature verification)

### Future Improvements
- [ ] Add Redis for cart persistence
- [ ] Implement webhook signature validation
- [ ] Add rate limiting
- [ ] Create admin dashboard
- [ ] Add analytics tracking
- [ ] Implement customer identification

## Migration Path

To fully migrate to production:

1. **Add Authentication**: Secure your endpoints
2. **Persistent Storage**: Move carts to Redis/database
3. **Error Handling**: Add comprehensive error tracking
4. **Monitoring**: Add APM and logging
5. **Testing**: Add integration tests for Retell flows

## Support

For questions about the refactor:
- Check archived code in `src/archive/`
- Review git history for original implementation
- Test with frontend interfaces
- Use ngrok for webhook testing