# Directory Organization Patterns

This guide covers how to organize files and directories to maintain clear boundaries, prevent circular dependencies, and support team ownership.

## Identifying False Domains

**Problem**: Folders that appear to be business domains but are actually cross-domain orchestration logic.

**Warning Signs of False Domains:**

- Folder primarily contains orchestration logic that coordinates other domains
- Services that only call other domain services without significant business logic
- Functionality could be moved to a main orchestrator without loss of clarity
- Folder name suggests a workflow rather than a business entity (e.g., `agent_setup/`, `user_onboarding/`)

**Example False Domain:**

```
app/features/retell/
├── agent_setup/              # 🚩 FALSE DOMAIN: Cross-domain orchestrator
│   ├── service.py           # Coordinates conversation_flows + voice_agents
│   ├── outbound_service.py  # Specialized workflow orchestration
│   └── admin_router.py      # Admin API endpoints
├── conversation_flows/       # ✅ True domain
├── voice_agents/             # ✅ True domain
```

**Solution**: Move cross-domain coordination to main feature orchestrator:

```
app/features/retell/
├── service.py                # Main orchestrator (consolidate agent_setup logic)
├── conversation_flows/       # True domain
├── voice_agents/             # True domain
└── admin_router.py           # Admin router (update imports)
```

**Benefits of Fixing False Domains:**

- ✅ **Clearer architecture** - orchestration is explicit, not hidden in fake domains
- ✅ **Better layering** - follows the established router → orchestrator → domain pattern
- ✅ **Easier maintenance** - coordination logic lives where expected
- ✅ **Prevents confusion** - new developers understand the true domain boundaries

## Vertical Slices + Integrations Hybrid

**Recommended Structure:**

```
app/
├── features/                   # Vertical slices - everything for a domain
│   ├── appointments/
│   │   ├── router.py
│   │   ├── service.py          # imports from integrations/
│   │   ├── models.py
│   │   └── schemas.py
│   └── retell/
│       ├── router.py, schemas.py
│       ├── templates/          # Domain submodule
│       │   ├── service.py      # Templates orchestrator (~300 LOC)
│       │   ├── loading_service.py, flow_service.py
│       │   ├── models.py, schemas.py
│       ├── voice_agents/       # Domain submodule
│       │   ├── service.py      # Voice agents orchestrator (~250 LOC)
│       │   ├── creation_service.py, management_service.py
│       │   ├── models.py, schemas.py
│       └── conversation_flow/  # Domain submodule
│           ├── service.py      # Flows orchestrator (~200 LOC)
│           ├── flow_service.py, validation_service.py
│           ├── models.py, schemas.py
├── integrations/               # Shared SDK wrappers
│   ├── retell/
│   │   └── client.py          # thin wrapper over Retell SDK
│   ├── calcom/
│   │   └── client.py          # thin wrapper over Cal.com API
│   └── database/
│       └── session.py
└── config/
    └── settings.py
```

## Models & Schemas Organization: Colocation vs Separation

**Current Stello AI Structure (Problematic for Vertical Slices):**

```
app/
├── models/              # All models in one place
│   ├── user.py, organization.py
│   ├── appointment.py, retell.py
│   ├── customer.py, schedule.py
│   └── ...
├── schemas/             # All schemas in one place
│   ├── organization.py
│   └── __init__.py
└── features/            # Features depend on global models
    ├── appointments/
    │   ├── service.py   # imports from app.models.appointment
    │   └── router.py    # imports from app.schemas.organization
    └── retell/
        └── service.py   # imports from app.models.retell
```

**Issues with Current Approach:**

- ❌ **Violates vertical slices** - features can't be self-contained
- ❌ **Unclear feature boundaries** - all models mixed together
- ❌ **Team ownership confusion** - who owns which models?
- ❌ **Harder to understand scope** - what models does a feature actually use?

**✅ Recommended Hybrid Approach:**

```
app/
├── models/              # Only truly shared/core models
│   ├── base.py         # Base model classes, mixins
│   ├── user.py         # Used across multiple features
│   ├── organization.py # Used across multiple features
│   └── __init__.py     # Common imports
├── features/            # Feature-specific models colocated
│   ├── appointments/
│   │   ├── models.py   # Appointment, Schedule models
│   │   ├── schemas.py  # Appointment API schemas
│   │   ├── service.py  # Clear feature scope
│   │   └── router.py
│   └── retell/
│       ├── models.py   # RetellConfiguration, VoiceAgent
│       ├── schemas.py  # Retell API schemas
│       ├── service.py
│       └── router.py
└── schemas/
    ├── shared.py       # Only shared response schemas
    └── __init__.py
```

**Decision Framework: Shared vs Feature Models**

**Keep in Global `models/` When:**

- ✅ **Used by 3+ features** (User, Organization)
- ✅ **Core domain entities** that define the business
- ✅ **Foreign key targets** referenced by many tables
- ✅ **Authentication/authorization** related models

**Move to Feature `models.py` When:**

- ✅ **Used by 1-2 features** (RetellConfiguration, Appointment)
- ✅ **Feature-specific configurations** (voice settings, scheduling rules)
- ✅ **Clear business domain boundary**
- ✅ **Could be owned by a single team**

**Migration Strategy for Stello AI:**

**Phase 1: Move Feature-Specific Models**

```bash
# Move feature-specific models to their domains
mv models/retell.py features/retell/models.py
mv models/appointment.py features/appointments/models.py
mv models/schedule.py features/appointments/models.py  # combine related
```

**Phase 2: Always Colocate Schemas**

```python
# app/features/retell/schemas.py
from .models import RetellConfiguration  # Local import
from app.models.organization import Organization  # Shared import

class RetellConfigResponse(BaseModel):
    config: RetellConfiguration
    organization: Organization
```

**Phase 3: Update Imports**

```python
# Before: Global imports
from app.models.retell import RetellConfiguration
from app.schemas.organization import OrgResponse

# After: Feature imports with clear boundaries
from app.features.retell.models import RetellConfiguration
from app.features.retell.schemas import RetellConfigResponse
from app.models.organization import Organization  # Still global - used by many features
```

**Benefits of Hybrid Approach:**

- ✅ **Clearer feature boundaries** - obvious what each feature owns
- ✅ **Better team ownership** - clear responsibility for models/schemas
- ✅ **Easier to understand scope** - feature folder contains everything needed
- ✅ **Shared models still centralized** - User/Organization remain global
- ✅ **Gradual migration path** - can move models incrementally

## Schema Placement Rules

Understanding where to place different types of schemas is critical for maintaining clean boundaries between internal APIs and external integrations.

### Internal API Schemas

**Location**: `app/features/[feature]/schemas.py`

**Purpose**: Define request/response models for your own API endpoints

```python
# app/features/calendar/schemas.py
from .models import EventType  # Local feature model
from app.models.organization import Organization  # Shared model

class CreateEventTypeRequest(BaseSchema):
    """Internal API - uses our domain language"""
    title: str
    duration_minutes: int  # Our field name
    custom_name: str | None
    schedule_id: str

class EventTypeInfo(BaseSchema):
    """Internal API response"""
    id: str
    title: str
    duration_minutes: int
    custom_name: str | None
    is_active: bool
```

### External API Schemas

**Location**: `app/integrations/[service]/schemas.py`

**Purpose**: Define models that match external service APIs exactly, with transformation methods

```python
# app/integrations/cal_com/schemas.py
class CalComEventTypePayload(CalComBaseSchema):
    """External API - matches Cal.com's exact format"""
    title: str
    length: int  # Their field name, not ours
    customName: str | None  # Their camelCase format
    minimumBookingNotice: int

    @classmethod
    def from_domain(cls, request: CreateEventTypeRequest):
        """Transform internal format to external API format"""
        return cls(
            title=request.title,
            length=request.duration_minutes,  # Field name mapping
            customName=request.custom_name,
            minimumBookingNotice=request.minimum_booking_notice,
        )

    def to_api_dict(self) -> dict:
        """Get dictionary ready for API call"""
        return self.model_dump(by_alias=True, exclude_none=True)
```

### Shared Base Schemas

**Location**: `app/schemas/base.py`

**Purpose**: Common base classes and utilities for all schemas

```python
# app/schemas/base.py
class BaseSchema(BaseModel):
    """Base for internal API schemas - automatic camelCase conversion"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True
    )

class CalComBaseSchema(BaseModel):
    """Base for Cal.com integration schemas"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        # Cal.com specific configuration
    )
```

### Schema Type Decision Matrix

| Schema Type                  | Location                    | Purpose                      | Example                  |
| ---------------------------- | --------------------------- | ---------------------------- | ------------------------ |
| **API Request/Response**     | `features/*/schemas.py`     | Validate your API endpoints  | `CreateEventTypeRequest` |
| **External API Integration** | `integrations/*/schemas.py` | Transform to external format | `CalComEventTypePayload` |
| **Base Classes**             | `schemas/base.py`           | Shared utilities             | `BaseSchema`             |
| **Database Models**          | `features/*/models.py`      | Database table definition    | `EventType(Base)`        |

### Key Rules

1. **Keep internal schemas in features** - They define your API contracts
2. **Keep external schemas in integrations** - They define external system contracts
3. **Use transformation methods** - `from_domain()` and `to_api_dict()` on external schemas
4. **Never mix formats** - Internal schemas use your domain language, external schemas match their APIs
5. **One source of truth** - Each external API gets exactly one schema file

## Nested Orchestrator Pattern

Each domain subfolder gets its own focused orchestrator that stays within guardrails (≤500 LOC, ≤8 operations):

```python
# ✅ GOOD: Focused orchestrator per subdomain
# app/features/retell/templates/service.py
class TemplateService:  # ~300 LOC, 5 operations
    """Orchestrates template operations only"""

    def __init__(self):
        self.loader = TemplateLoadingService()
        self.flow_creator = FlowCreationService()

    async def create_complete_template_flow(self, config):
        # Thin orchestration within templates domain
        template = await self.loader.load_template(config.name)
        flow = await self.flow_creator.create_flow(template)
        return TemplateFlowResult(template, flow)
```

**When to Use Nested vs Top-Level Orchestrators:**

✅ **Keep Nested Orchestrators When:**

- Each subdomain has 3-8 independent operations
- Different teams own different subdomains
- Subdomains rarely interact
- Each orchestrator stays <500 LOC

```python
# Independent operations - keep nested
templates/service.py      # Template CRUD + customization
voice_agents/service.py   # Agent creation + management
conversation_flow/service.py # Flow creation + validation
```

⚠️ **Consider Top-Level Orchestrator When:**

- Complex workflows span multiple subdomains
- Shared transactions across subdomains
- Any nested orchestrator exceeds 500 LOC

```python
# app/features/retell/service.py - Only if you have cross-domain workflows
class RetellService:
    def __init__(self):
        self.templates = TemplateService()
        self.agents = VoiceAgentService()
        self.flows = ConversationFlowService()

    async def create_complete_voice_assistant(self, config):
        """Cross-domain workflow requiring coordination"""
        async with db.transaction():
            template = await self.templates.create_template(config.template_data)
            flow = await self.flows.create_flow(template)
            agent = await self.agents.create_agent(flow, config.voice_settings)
            return CompleteAssistant(template, flow, agent)
```

## Testing Organization

**Test Organization Example:**

```
src/features/dashboard/tests/  ← Flat structure, no subfolders
├── organizationService.test.ts     ← API/service tests
├── BusinessInformation.test.tsx    ← Component + hook integration
└── BusinessInformationFlow.test.tsx ← User journey tests
```

**Frontend Structure (`clients/web_portal/`):**

```
src/
├── features/          # Feature-based organization (auth/, dashboard/, onboarding/, etc.)
│   └── [feature]/     # Each follows the pattern below
├── components/        # Shared/global components
│   ├── guards/        # Route protection (RequireAuth, etc.)
│   └── ui/            # Base UI components (shadcn/ui style)
├── shared/            # Cross-cutting concerns
│   ├── components/    # Utility components (Clock, etc.)
│   └── contexts/      # Global React contexts
├── config/            # App configuration (Firebase, etc.)
├── lib/               # Utility functions
└── mocks/             # MSW API mocking for tests
```

**Feature Organization Pattern:**
Each feature follows: `components/` → `hooks/` → `services/` → `types/` → `tests/` → `index.ts`

**Backend Structure (`servers/core-api/`):**

```
app/
├── features/          # Domain-driven feature modules (auth/, organizations/, onboarding/, etc.)
│   └── [feature]/     # Each follows the pattern below
├── core/              # Cross-cutting concerns
│   ├── auth.py        # Authentication middleware & utilities
│   ├── dependencies.py # FastAPI dependency injection
│   ├── middleware.py  # Request/response middleware
│   └── roles.py       # Role-based access control
├── models/            # SQLAlchemy database models
├── integrations/      # External service integrations
└── main.py            # FastAPI application entry point
```

**Feature Module Pattern:**
Each feature contains: `models.py` → `schemas.py` → `service.py` → `router.py` → `dependencies.py`

### Admin API Pattern Exception

When a feature has both user-facing and admin endpoints with significantly different schemas, use parallel admin files:

**Standard Pattern:**

```
app/features/retell/
├── models.py           # Database models (shared)
├── schemas.py          # User-facing API schemas
├── service.py          # Business logic
├── router.py           # User endpoints
└── dependencies.py     # Dependencies
```

**With Admin APIs:**

```
app/features/retell/
├── models.py           # Database models (shared)
├── schemas.py          # User-facing API schemas
├── admin_schemas.py    # Admin-only schemas with extended fields ✅
├── service.py          # Business logic
├── router.py           # User endpoints
├── admin_router.py     # Admin endpoints ✅
└── dependencies.py     # Dependencies
```

**When to Use Admin Pattern:**

✅ **Use admin files when:**

- Admin endpoints need different response fields (e.g., `organization_name`, `quality_issues`)
- Admin schemas extend user schemas with cross-tenant data
- Clear separation improves developer understanding

❌ **Don't use admin files when:**

- Admin access is just permission-based (use dependencies instead)
- Schemas are identical (just different authorization)

**Import Pattern:**

```python
# admin_router.py
from app.features.retell import admin_schemas, schemas

@router.get("/calls", response_model=admin_schemas.AdminCallListResponse)
async def list_all_calls(...):
    # Construct admin schema objects
    calls = [admin_schemas.AdminCallInfo(...) for row in rows]
    return admin_schemas.AdminCallListResponse(calls=calls)

# router.py (user endpoints)
from app.features.retell import schemas

@router.get("/calls", response_model=schemas.CallListResponse)
async def list_my_calls(...):
    # Uses regular schemas
    calls = [schemas.CallInfo(...) for row in rows]
    return schemas.CallListResponse(calls=calls)
```

**Benefits:**

- ✅ Clear separation of admin vs user schemas
- ✅ Pattern consistency (matches `admin_router.py` convention)
- ✅ Admin schemas can have extra fields without polluting user API
- ✅ Easy to see which schemas are admin-only

**Real Example:** `app/features/retell/` has:

- `schemas.CallInfo` - user schema (14 fields)
- `admin_schemas.AdminCallInfo` - admin schema (19 fields including `organization_name`, `quality_issues`)

## Import Hierarchy & Dependency Rules

**Stello follows strict layered architecture to prevent circular dependencies and maintain clean separation of concerns.**

### Layer Hierarchy (Bottom-Up)

```
┌─────────────────────────────────────────┐
│ Router Layer (FastAPI routes)          │ ← Can import everything below
├─────────────────────────────────────────┤
│ Dependencies Layer (DI, auth context)  │ ← Can import services + models + config
├─────────────────────────────────────────┤
│ Services Layer (business logic)        │ ← Can import integrations + models + config
├─────────────────────────────────────────┤
│ Integrations Layer (external APIs)     │ ← Can import config + utilities only
├─────────────────────────────────────────┤
│ Config/Utilities Layer                 │ ← Can import standard libraries only
├─────────────────────────────────────────┤
│ Models Layer (SQLAlchemy models)       │ ← Imports NOTHING from app layers
└─────────────────────────────────────────┘
```

### Import Rules (ENFORCE STRICTLY)

**Models Layer**: `app/models/`, `app/features/*/models.py`

- ✅ **CAN** import: `app.database.Base`, `app.models.base` mixins, other models for relationships
- ❌ **CANNOT** import: Services, dependencies, routers, or any feature logic

**Config/Utilities Layer**: `app/core/config.py`, `app/core/logging.py`, `app/utils/`

- ✅ **CAN** import: Standard libraries (os, logging, datetime)
- ❌ **CANNOT** import: Any app layers (models, services, etc.)

**Integrations Layer**: `app/integrations/`

- ✅ **CAN** import: Config, utilities, external libraries (requests, httpx)
- ❌ **CANNOT** import: Models, services, dependencies, routers

**Services Layer**: `app/features/*/service.py`

- ✅ **CAN** import: Models, integrations, config, utilities
- ❌ **CANNOT** import: Dependencies (FastAPI Depends), routers

**Dependencies Layer**: `app/core/dependencies.py`, feature dependency modules

- ✅ **CAN** import: Models, services, config, utilities
- ❌ **CANNOT** import: Routers

**Router Layer**: `app/features/*/router.py`

- ✅ **CAN** import: Everything (models, services, dependencies)

### Model Registration Pattern

**All models MUST be imported in `app/models/__init__.py` for Alembic discovery:**

```python
# app/models/__init__.py
from app.features.calendar.models import Appointment, Schedule
from app.features.pixel.models import PixelEvent
from app.features.retell.models import RetellConfiguration, RetellCallLog, TrainingFile
```

**Feature `__init__.py` files should NOT import routers to avoid circular dependencies:**

```python
# ✅ GOOD: app/features/calendar/__init__.py
# Router moved to main app registration to avoid circular dependencies

# ❌ BAD: Don't do this
# from app.features.calendar.router import router  # Creates circular dependency!
```

### Benefits of This Architecture

- 🚫 **Prevents circular dependencies** - Clear import hierarchy
- 🔄 **Enables Alembic model discovery** - All models centrally registered
- 🧪 **Improves testability** - Clear layer boundaries
- 👥 **Scales with team growth** - Explicit rules about what imports what
- 🐛 **Easier debugging** - Predictable dependency flow

## Key Integration Points

- **Type Safety**: Backend Pydantic → OpenAPI → TypeScript types → Frontend
- **Authentication**: Firebase Auth (frontend) ↔ Firebase Admin SDK (backend)
- **API Communication**: Axios (frontend) ↔ FastAPI (backend)
- **Database**: SQLAlchemy models ↔ Alembic migrations ↔ PostgreSQL
- **Development**: Docker Compose orchestrates all services locally

## Related Guides

- [Service Architecture](service-architecture.md) - How to design the services within these directory structures
- [Integration Patterns](integration-patterns.md) - How to organize external service integrations
- [Decision Frameworks](decision-frameworks.md) - Decision matrices for when to move models or restructure directories
