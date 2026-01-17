# Clean Code Review & Refactoring Plan

## Summary

Analysis against Stello AI Clean Code Standards revealed **23 violations**. This document includes both the findings and the refactoring plan to address them.

| Category | Violations | Severity |
|----------|-----------|----------|
| Service Architecture | 6 | HIGH |
| Directory Organization | 10 | MEDIUM-HIGH |
| Integration Patterns | 7 | HIGH-CRITICAL |

**Key Finding:** No actual circular dependencies exist. The architecture flows correctly (Infrastructure → Orchestration → Domains → Shared). Issues are about code organization and service size.

---

# Part 1: Violations Found

## 1. Service Architecture Violations

### 1.1 Fat Service: ShopifyClient (HIGH)
**File:** `backend/src/domains/shopify/client.py` (318 LOC)
- **9 public methods** (exceeds 8-operation limit)
- **Multiple domains:** Products, inventory, carts, collections in one class

### 1.2 Fat Service: VoiceAgent (HIGH)
**File:** `backend/src/orchestration/agent/graph.py` (441 LOC)
- **9+ public methods** (exceeds limit)
- **Multiple concerns:** Intent detection, tool selection, tool execution, response generation

### 1.3 Fat WebSocket Handler (CRITICAL)
**File:** `backend/src/infrastructure/api/routes.py`
- `voice_session()` is **276 lines**
- Contains: session management, message dispatching, TTS calls, interrupt handling

### 1.4 Service-to-Service Calls (HIGH)
**File:** `backend/src/domains/shopify/products.py`
- ProductService directly calls ShopifyClient (7+ direct calls)

## 2. Directory Organization Violations

### 2.1 False Domain: `orchestration/` (HIGH)
**Location:** `backend/src/orchestration/`
- Acts as pure workflow layer, not a vertical slice domain
- Should be eliminated - contents moved to proper domains

### 2.2 Business Logic in API Client (HIGH)
**File:** `backend/src/domains/shopify/client.py`
- `search_products()` contains filtering/scoring logic (belongs in service layer)
- Date parsing duplicated 3 times across methods

## 3. Integration Pattern Violations

### 3.1 Data Transformation in Client (HIGH)
**File:** `backend/src/domains/shopify/client.py`
- ~60 lines of duplicated date/price parsing across methods
- Should be extracted to mappers

---

# Part 2: Refactoring Plan

## Scope
Pure refactoring only - no new features. Focus on code organization for future scalability.

---

## Phase 1: Extract Shopify Data Mappers

**Goal:** Remove ~60 lines of duplicated transformation code

### Create: `backend/src/domains/shopify/mappers.py`

```python
from datetime import datetime

def parse_shopify_datetime(value: str | None) -> datetime | None:
    """Convert Shopify ISO datetime (with Z suffix) to Python datetime."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def transform_variant(variant: dict) -> dict:
    """Transform variant dates and prices."""
    variant["created_at"] = parse_shopify_datetime(variant.get("created_at"))
    variant["updated_at"] = parse_shopify_datetime(variant.get("updated_at"))
    variant["price"] = float(variant["price"]) if variant.get("price") else 0.0
    if variant.get("compare_at_price"):
        variant["compare_at_price"] = float(variant["compare_at_price"])
    return variant

def transform_product(product: dict) -> dict:
    """Transform product response from Shopify API."""
    product["created_at"] = parse_shopify_datetime(product.get("created_at"))
    product["updated_at"] = parse_shopify_datetime(product.get("updated_at"))
    product["published_at"] = parse_shopify_datetime(product.get("published_at"))

    for variant in product.get("variants", []):
        transform_variant(variant)

    for image in product.get("images", []):
        image["created_at"] = parse_shopify_datetime(image.get("created_at"))
        image["updated_at"] = parse_shopify_datetime(image.get("updated_at"))

    return product

def transform_collection(collection: dict) -> dict:
    """Transform collection response."""
    collection["created_at"] = parse_shopify_datetime(collection.get("created_at"))
    collection["updated_at"] = parse_shopify_datetime(collection.get("updated_at"))
    collection["published_at"] = parse_shopify_datetime(collection.get("published_at"))
    return collection
```

### Modify: `backend/src/domains/shopify/client.py`
- Replace inline transformation with mapper calls

---

## Phase 2: Split ShopifyClient

**Goal:** Split 318 LOC / 9 methods into focused clients under 8 methods each

### Create: `backend/src/domains/shopify/base_client.py`
- `ShopifyBaseClient` with `__init__`, `close()`, `_request()` (~100 LOC)

### Create: `backend/src/domains/shopify/products_client.py`
- `ProductsClient(ShopifyBaseClient)` with `get_products`, `get_product`, `get_collections` (~120 LOC)

### Create: `backend/src/domains/shopify/inventory_client.py`
- `InventoryClient(ShopifyBaseClient)` with `get_inventory_levels` (~50 LOC)

### Create: `backend/src/domains/shopify/carts_client.py`
- `CartsClient(ShopifyBaseClient)` with `create_cart`, `update_cart` (~60 LOC)

### Modify: `backend/src/domains/shopify/client.py`
Keep as facade for backward compatibility:
```python
from .products_client import ProductsClient
from .inventory_client import InventoryClient
from .carts_client import CartsClient

class ShopifyClient(ProductsClient, InventoryClient, CartsClient):
    """Unified Shopify client (facade for backward compatibility)."""
    pass
```

---

## Phase 3: Move Search Logic to Service Layer

**Goal:** Remove business logic from API client

### Modify: `backend/src/domains/shopify/products_client.py`
- Remove `search_products()` method (it has business logic)

### Modify: `backend/src/domains/shopify/products.py`
- Add `search_products()` method to `ProductService`:
```python
async def search_products(self, query: str, limit: int = 10) -> list[Product]:
    """Search products by query (business logic belongs here)."""
    all_products = await self.client.get_products(limit=250)
    query_lower = query.lower()
    matching = []

    for product in all_products:
        if (query_lower in product.title.lower() or
            any(query_lower in tag.lower() for tag in product.tags)):
            matching.append(self._to_domain_product(product))

    return matching[:limit]
```

---

## Phase 4: Flatten Infrastructure to Root

**Goal:** Simplify by removing unnecessary nesting

### Move files to root:
- `infrastructure/api/app.py` → `app.py`
- `infrastructure/api/routes.py` → `routes.py`
- `infrastructure/config/settings.py` → `config.py`

### Delete:
- `infrastructure/` folder entirely
- `infrastructure/tts/` (Retell handles TTS)

### Update imports in moved files:
```python
# Before (in routes.py)
from infrastructure.config.settings import get_settings

# After
from config import get_settings
```

---

## Phase 5: Eliminate `orchestration/` Folder

**Goal:** Remove false domain, move contents to proper vertical slices

### Current Structure:
```
orchestration/
├── agent/
│   ├── graph.py           # VoiceAgent
│   ├── optimized_agent.py # OptimizedVoiceAgent
│   ├── prompts.py         # LLM prompts
│   └── fast_voice_agent.py
└── tools/
    ├── base.py            # BaseTool, ToolContext
    ├── registry.py        # ToolRegistry
    └── product_tools.py   # Product-specific tools
```

### New Structure:
```
domains/
├── voice/
│   ├── agent/
│   │   ├── graph.py
│   │   ├── optimized_agent.py
│   │   ├── fast_voice_agent.py
│   │   └── prompts.py
│   ├── tools/
│   │   ├── base.py
│   │   └── registry.py
│   └── pipeline.py        # (existing)
│
└── shopify/
    ├── tools/
    │   └── product_tools.py  # Shopify-specific tools
    ├── client.py
    ├── products.py
    └── ...
```

### Migration Steps:

1. **Create `domains/voice/agent/`**
   - Move `orchestration/agent/*` → `domains/voice/agent/`

2. **Create `domains/voice/tools/`**
   - Move `orchestration/tools/base.py` → `domains/voice/tools/base.py`
   - Move `orchestration/tools/registry.py` → `domains/voice/tools/registry.py`

3. **Create `domains/shopify/tools/`**
   - Move `orchestration/tools/product_tools.py` → `domains/shopify/tools/product_tools.py`

4. **Update all imports** across the codebase:
   - `from orchestration.agent.optimized_agent` → `from domains.voice.agent.optimized_agent`
   - `from orchestration.tools.registry` → `from domains.voice.tools.registry`
   - `from orchestration.tools.product_tools` → `from domains.shopify.tools.product_tools`

5. **Delete `orchestration/` folder**

### Files to Update Imports:
- `infrastructure/api/app.py`
- `infrastructure/api/routes.py`
- `infrastructure/livekit/agent.py`

---

## File Summary

| Action | File |
|--------|------|
| **Shopify Domain** | |
| CREATE | `domains/shopify/mappers.py` |
| CREATE | `domains/shopify/base_client.py` |
| CREATE | `domains/shopify/products_client.py` |
| CREATE | `domains/shopify/inventory_client.py` |
| CREATE | `domains/shopify/carts_client.py` |
| MODIFY | `domains/shopify/client.py` (facade) |
| MODIFY | `domains/shopify/products.py` (add search) |
| MODIFY | `domains/shopify/types.py` (colocate Shopify types) |
| MOVE | `orchestration/tools/product_tools.py` → `domains/shopify/tools/` |
| **Voice Domain** | |
| MOVE | `orchestration/agent/*` → `domains/voice/agent/` |
| MOVE | `orchestration/tools/base.py` → `domains/voice/tools/` |
| MOVE | `orchestration/tools/registry.py` → `domains/voice/tools/` |
| CREATE | `domains/voice/retell_handler.py` |
| CREATE | `domains/voice/types.py` (colocate voice types) |
| **Integrations** | |
| CREATE | `integrations/retell/__init__.py` |
| CREATE | `integrations/retell/client.py` |
| CREATE | `integrations/retell/types.py` |
| **Root Level (flattened)** | |
| MOVE | `infrastructure/api/app.py` → `app.py` |
| MOVE | `infrastructure/api/routes.py` → `routes.py` |
| MOVE | `infrastructure/config/settings.py` → `config.py` |
| MOVE | `shared/utils.py` → `utils.py` |
| **Schemas (renamed from shared/)** | |
| RENAME | `shared/` → `schemas/` |
| MOVE | `shared/types.py` → `schemas/common.py` (only cross-domain) |
| KEEP | `schemas/exceptions.py` |
| **Deleted** | |
| DELETE | `infrastructure/` folder |
| DELETE | `orchestration/` folder |

**Total: 12 new files, 7 moved files, 5 modified files, 2 folders deleted, 1 folder renamed**

---

## Execution Order

1. **Phase 1** - Mappers (no dependencies, safe first step)
2. **Phase 2** - ShopifyClient split (update client.py last for backward compat)
3. **Phase 3** - Move search logic (depends on Phase 2)
4. **Phase 4** - WebSocket extraction (independent of Shopify changes)
5. **Phase 5** - Eliminate orchestration folder (move to domains/)
6. **Phase 6** - Replace LiveKit with Retell (do after Phase 5, since voice/ moves first)

---

## Verification

After each phase:
```bash
# Import checks
python -c "from domains.shopify.client import ShopifyClient"
python -c "from routes import router"
python -c "from domains.voice.agent.optimized_agent import OptimizedVoiceAgent"
python -c "from integrations.retell.client import RetellClient"

# Run existing tests
pytest tests/
```

---

## Phase 6: Replace LiveKit with Retell

**Goal:** Simplify voice infrastructure by using Retell's unified platform instead of LiveKit's modular approach.

### Why Retell?
- **Speed**: Retell optimizes for low-latency voice AI
- **Simplicity**: Built-in STT, TTS, VAD - no plugin management
- **Less code**: Retell handles the voice pipeline, you focus on business logic

### Current LiveKit Setup

```
infrastructure/livekit/
├── __init__.py
└── agent.py           # 236 LOC - LiveKitVoiceAgent

LiveKit provides:
├── WebRTC transport
├── VAD (Silero plugin)
├── STT (Deepgram/OpenAI plugins)
├── TTS (Cartesia/OpenAI plugins)
└── Session management (rooms)
```

**Dependencies to remove:**
```
livekit = "^0.8.0"
livekit-agents = "^0.8.0"
livekit-plugins-openai = "^0.5.0"
livekit-plugins-silero = "^0.5.0"
livekit-plugins-deepgram = "^0.5.0"
livekit-plugins-cartesia = "^0.5.0"
```

### New Retell Setup

```
integrations/retell/
├── __init__.py
├── client.py          # Retell SDK wrapper (thin client)
└── schemas.py         # Retell-specific schemas

domains/voice/
├── agent/             # Keep existing agent logic
├── tools/             # Keep tool registry
└── retell_handler.py  # NEW: Retell webhook/event handler
```

**Dependencies to add:**
```
retell-sdk = "^X.X.X"  # Retell Python SDK
```

### Migration Steps

#### Step 1: Add Retell Configuration
**Modify:** `backend/src/infrastructure/config/settings.py`

```python
# Remove LiveKit settings
# livekit_url, livekit_api_key, livekit_api_secret, livekit_room_prefix

# Add Retell settings
retell_api_key: str = Field(alias="RETELL_API_KEY")
retell_agent_id: str | None = Field(default=None, alias="RETELL_AGENT_ID")

def get_retell_config(self) -> dict:
    return {
        "api_key": self.retell_api_key,
        "agent_id": self.retell_agent_id,
    }
```

#### Step 2: Create Retell Integration Client
**Create:** `backend/src/integrations/retell/client.py`

```python
from retell import Retell

class RetellClient:
    """Thin wrapper over Retell SDK."""

    def __init__(self, api_key: str):
        self.client = Retell(api_key=api_key)

    async def create_web_call(self, agent_id: str, metadata: dict = None) -> dict:
        """Create a web call session."""
        response = self.client.call.create_web_call(
            agent_id=agent_id,
            metadata=metadata or {}
        )
        return {"call_id": response.call_id, "access_token": response.access_token}

    async def create_phone_call(self, agent_id: str, to_number: str) -> dict:
        """Create an outbound phone call."""
        response = self.client.call.create_phone_call(
            from_number=self.from_number,
            to_number=to_number,
            agent_id=agent_id
        )
        return {"call_id": response.call_id}

    async def end_call(self, call_id: str) -> bool:
        """End an active call."""
        self.client.call.end(call_id=call_id)
        return True
```

#### Step 3: Create Retell Webhook Handler
**Create:** `backend/src/domains/voice/retell_handler.py`

```python
class RetellWebhookHandler:
    """Handles Retell webhooks for tool calling."""

    def __init__(self, tool_registry):
        self.registry = tool_registry

    async def handle_llm_webhook(self, request: dict) -> dict:
        """
        Handle Retell's LLM webhook for custom responses.
        Called when Retell needs tool execution.
        """
        call_id = request.get("call_id")
        transcript = request.get("transcript", [])

        # Check for function calls
        if request.get("function_call"):
            func_name = request["function_call"]["name"]
            func_args = request["function_call"]["arguments"]

            # Execute tool via existing registry
            tool = self.registry.get(func_name)
            if tool:
                result = await tool.execute(**func_args)
                return {
                    "response_type": "function_result",
                    "function_result": result.data
                }

        # Return empty for normal LLM flow
        return {"response_type": "agent_response"}
```

#### Step 4: Update API Routes
**Modify:** `backend/src/routes.py` (now at root level)

```python
# Add Retell endpoints

@router.post("/api/calls/web")
async def create_web_call(request: CreateWebCallRequest):
    """Create a Retell web call session."""
    settings = get_settings()
    retell = RetellClient(settings.retell_api_key)
    return await retell.create_web_call(
        agent_id=settings.retell_agent_id,
        metadata={"user_id": request.user_id}
    )

@router.post("/api/retell/webhook")
async def retell_webhook(request: Request):
    """Handle Retell LLM webhooks for tool calling."""
    data = await request.json()
    handler = RetellWebhookHandler(registry)
    return await handler.handle_llm_webhook(data)
```

#### Step 5: Clean Up
**Delete:**
- `infrastructure/livekit/` folder
- `infrastructure/tts/` folder (Retell handles TTS)
- Old WebSocket voice session code (Retell replaces it)

**Modify:** `pyproject.toml`
- Remove all `livekit*` dependencies
- Remove `cartesia` dependency
- Add `retell-sdk`

### Architecture Comparison

**Before (LiveKit):**
```
Client (WebRTC)
    ↓
LiveKit Server (self-hosted or cloud)
    ↓
LiveKitVoiceAgent worker
    ├→ Silero VAD
    ├→ Deepgram STT
    ├→ OpenAI LLM
    ├→ Cartesia TTS
    └→ Tool Registry
```

**After (Retell):**
```
Client (Web SDK / Phone)
    ↓
Retell Cloud (managed)
    ↓ webhook
Your Server
    └→ RetellWebhookHandler
        └→ Tool Registry (existing)
```

### What You Keep
- Tool registry and all product tools
- Business logic in domains/shopify/
- Conversation context management
- OpenAI LLM integration (Retell uses it too)

### What You Remove
- All LiveKit code and dependencies
- Custom VAD/STT/TTS plugin management
- WebRTC room management
- Separate LiveKit worker process

### Files Summary for Phase 6

| Action | File |
|--------|------|
| DELETE | `infrastructure/livekit/` folder |
| DELETE | `infrastructure/tts/` folder |
| CREATE | `integrations/retell/__init__.py` |
| CREATE | `integrations/retell/client.py` |
| CREATE | `domains/voice/retell_handler.py` |
| MODIFY | `config.py` (add Retell settings) |
| MODIFY | `routes.py` (add Retell endpoints, remove old WebSocket) |
| MODIFY | `pyproject.toml` (swap dependencies) |

---

## Out of Scope (New Features, Not Refactoring)

- TTS cost tracking/compensation
- Rate limiting
- Quota management
- New test coverage

---

## Directory Structure After Refactoring

```
backend/src/
├── app.py              # FastAPI app
├── routes.py           # API routes
├── config.py           # Settings
├── main.py             # Entry point
│
├── domains/
│   ├── shopify/
│   │   ├── base_client.py      # Shared HTTP logic
│   │   ├── products_client.py  # Product operations
│   │   ├── inventory_client.py # Inventory operations
│   │   ├── carts_client.py     # Cart operations
│   │   ├── client.py           # Facade for backward compat
│   │   ├── mappers.py          # Data transformation
│   │   ├── products.py         # Product service
│   │   ├── types.py            # Shopify-specific types (colocated)
│   │   └── tools/
│   │       └── product_tools.py
│   │
│   └── voice/
│       ├── agent/
│       │   ├── optimized_agent.py
│       │   └── prompts.py
│       ├── tools/
│       │   ├── base.py
│       │   └── registry.py
│       ├── types.py            # Voice-specific types (colocated)
│       └── retell_handler.py
│
├── integrations/
│   └── retell/
│       ├── __init__.py
│       ├── client.py           # Thin SDK wrapper
│       └── types.py            # Retell-specific types (colocated)
│
├── schemas/                    # Only cross-domain schemas (renamed from shared/)
│   ├── __init__.py
│   ├── common.py               # Truly shared types (Message, etc.)
│   └── exceptions.py           # Shared exceptions
│
└── utils.py                    # Simple utilities (flattened)

# DELETED:
# - infrastructure/           (flattened to root)
# - orchestration/            (moved to domains/)
# - shared/                   (renamed to schemas/, types colocated)
```

---

## Reference

See `CLEAN_CODE_GUIDE/` for the full clean code standards documentation.
