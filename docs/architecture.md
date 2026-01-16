# Architecture Overview

## System Design

The Voice Sales Agent follows Domain-Driven Design (DDD) principles with clear separation of concerns.

```
┌─────────────────────────────────────────────────────┐
│                   Voice Interface                    │
│                    (LiveKit Agent)                   │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                  Voice Pipeline                      │
│              (STT → LLM → TTS)                      │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│               LangGraph Agent                        │
│         (Routing & Tool Orchestration)               │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                    Tools Layer                       │
│   ┌──────────┬──────────┬──────────┬──────────┐   │
│   │ Product  │   Cart   │  Sizing  │ Policies │   │
│   │  Tools   │  Tools   │  Tools   │  Tools   │   │
│   └──────────┴──────────┴──────────┴──────────┘   │
└─────────────────┬───────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────┐
│                  Domain Layer                        │
│   ┌──────────┬──────────┬──────────┬──────────┐   │
│   │ Shopify  │ Products │   Cart   │  Sizing  │   │
│   │  Domain  │  Domain  │  Domain  │  Domain  │   │
│   └──────────┴──────────┴──────────┴──────────┘   │
└──────────────────────────────────────────────────────┘
```

## Directory Structure

```
backend/
├── src/
│   ├── domains/           # Pure business logic
│   ├── orchestration/     # Agent and tools
│   ├── infrastructure/    # External integrations
│   └── shared/           # Common utilities
```

## Core Principles

### 1. Tool-First Architecture

The agent NEVER directly calls domains or external services. All actions go through tools:

```python
# CORRECT: Agent uses tools
response = await agent.invoke_tool("search_products", {"query": "red shoes"})

# WRONG: Agent calls domain directly
products = await shopify_domain.search_products("red shoes")
```

### 2. Domain Isolation

Domains contain pure business logic with no external dependencies:

```python
# Domain: Pure business logic
class ProductSearch:
    def rank_products(self, products: List[Product]) -> List[Product]:
        # Pure logic, no API calls
        return sorted(products, key=lambda p: p.relevance_score)

# Infrastructure: External integrations
class ShopifyClient:
    async def fetch_products(self) -> List[dict]:
        # API calls here
        return await self.api.get("/products")
```

### 3. Voice as a Domain

Voice processing is treated as a business domain, not infrastructure:

```python
# domains/voice/pipeline.py
class VoicePipeline:
    async def process(self, audio: bytes) -> str:
        transcript = await self.transcribe(audio)
        response = await self.generate_response(transcript)
        audio_response = await self.synthesize(response)
        return audio_response
```

### 4. Cascading Pipeline

Voice processing follows a strict sequential flow:

1. **Speech-to-Text (STT)**: Convert audio to text
2. **LLM Processing**: Generate response via agent
3. **Text-to-Speech (TTS)**: Convert response to audio

## Agent Architecture

### LangGraph Structure

```python
# Simplified agent graph
graph = StateGraph(AgentState)

# Add nodes
graph.add_node("router", route_intent)
graph.add_node("product_search", handle_product_search)
graph.add_node("cart_ops", handle_cart_operations)

# Add edges
graph.add_conditional_edges(
    "router",
    determine_next_node,
    {
        "product": "product_search",
        "cart": "cart_ops",
    }
)
```

### Tool Registry

Tools are dynamically registered and discovered:

```python
@register_tool("search_products")
class SearchProductsTool(BaseTool):
    async def execute(self, query: str) -> List[Product]:
        # Tool implementation
        pass
```

## Data Flow

### Request Flow

1. **Voice Input** → LiveKit receives audio
2. **Transcription** → Convert to text via STT
3. **Intent Detection** → Agent determines intent
4. **Tool Selection** → Agent selects appropriate tool(s)
5. **Tool Execution** → Tools interact with domains
6. **Response Generation** → Agent formulates response
7. **Speech Synthesis** → Convert to audio via TTS
8. **Voice Output** → LiveKit sends audio response

### State Management

```python
class ConversationState:
    session_id: str
    messages: List[Message]
    context: Dict[str, Any]
    cart: Cart
    user_preferences: UserPreferences
```

## Extensibility

### Adding New Capabilities

1. **Create Domain** (if needed)
   ```python
   # domains/recommendations/engine.py
   class RecommendationEngine:
       def get_recommendations(self, user: User) -> List[Product]:
           pass
   ```

2. **Create Tool**
   ```python
   # orchestration/tools/recommendation_tools.py
   @register_tool("get_recommendations")
   class GetRecommendationsTool(BaseTool):
       async def execute(self, user_id: str) -> List[Product]:
           pass
   ```

3. **Update Agent** (if routing needed)
   ```python
   # orchestration/agent/router.py
   def determine_intent(state: AgentState) -> str:
       if "recommend" in state.last_message:
           return "recommendations"
   ```

## Performance Considerations

### Caching Strategy

- Product catalog cached for 5 minutes
- User session cached for duration
- Voice responses cached for repeated questions

### Async Processing

All I/O operations are async:
- API calls
- Database queries
- Voice processing

### Resource Management

- Connection pooling for Shopify API
- Rate limiting for external services
- Memory-efficient streaming for audio