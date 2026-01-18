# API Design Patterns

This guide covers API design patterns, orchestration decisions, and the three-layer approach for building maintainable APIs.

## Router + Service Orchestration Pattern (Stello AI Standard)

**Stello AI uses a sophisticated three-layer approach that balances simplicity with flexibility:**

```python
# Layer 1: Thin Router - Pure HTTP delegation
@router.get("/", response_model=schemas.VoiceAgentsListResponse)
async def list_voice_agents(org_context: OrganizationContextDep, db: DatabaseDep):
    """List all voice agents for organization - thin delegation"""
    service = get_voice_agent_service()
    return await service.list_agents_for_organization(org_context.organization_id, db)

@router.post("/", response_model=schemas.VoiceAgentCreateResponse)
async def create_voice_agent(request: schemas.VoiceAgentCreateRequest, org_context: OrganizationContextDep, db: DatabaseDep):
    """Create a new voice agent - thin delegation"""
    service = get_voice_agent_service()
    return await service.create_agent_for_organization(request, org_context.organization_id, db)
```

```python
# Layer 2: Main Orchestrator Service - Coordinates specialized services
class VoiceAgentService:
    """Main orchestrator for voice agent operations (~250 LOC, <8 operations)"""

    def __init__(self):
        self.creation_service = VoiceAgentCreationService()
        self.configuration_service = VoiceAgentConfigurationService()
        self.retrieval_service = VoiceAgentRetrievalService()
        self.deletion_service = VoiceAgentDeletionService()

    # Simple CRUD operations - delegate to specialized services
    async def list_agents_for_organization(self, organization_id: str, db: AsyncSession) -> schemas.VoiceAgentsListResponse:
        """Thin delegation to retrieval service"""
        result = await self.retrieval_service.get_agents_by_organization(organization_id, db)
        return schemas.VoiceAgentsListResponse(success=True, agents=result["agents"])

    # Intent-driven operations - orchestrate multiple services
    async def complete_agent_onboarding(self, request: AgentOnboardingRequest, org_id: str, db: AsyncSession) -> AgentOnboardingResponse:
        """Intent: Get user from idea to working agent"""
        try:
            # Orchestrate business workflow
            template = await self.template_service.create_from_business_info(request.business_info)
            flow = await self.flow_service.create_from_template(template, org_id)
            agent = await self.creation_service.create_agent_from_flow_id(
                flow.id, request.agent_name, request.voice_id, org_id, api_base_url
            )
            phone = await self.phone_service.assign_number(agent["agent_id"], org_id)

            return AgentOnboardingResponse(
                success=True,
                agent=agent,
                flow=flow,
                phone=phone,
                message="Complete agent setup created successfully"
            )
        except Exception as e:
            # Compensation pattern for external API failures
            await self._cleanup_partial_onboarding(template, flow, agent, phone)
            raise AgentOnboardingError(f"Onboarding failed: {str(e)}")
```

```python
# Layer 3: Specialized Domain Services - Single responsibility
class VoiceAgentCreationService:
    """Pure voice agent creation - no template knowledge (~150 LOC, <5 operations)"""

    async def create_agent_from_flow_id(self, flow_id: str, agent_name: str, voice_id: str,
                                       organization_id: str, api_base_url: str) -> dict[str, Any]:
        """Create agent from existing conversation flow - pure agent CRUD"""
        agent_service = self._get_agent_service()

        try:
            response_engine = ResponseEngineResponseEngineConversationFlow(
                type="conversation-flow", conversation_flow_id=flow_id
            )
            webhook_url = f"{api_base_url}/api/v1/retell/webhook?organization_id={organization_id}"

            agent_result = await agent_service.create_agent(
                agent_name=agent_name, voice_id=voice_id, language="en-US",
                webhook_url=webhook_url, response_engine=response_engine
            )

            return {"success": True, "agent_id": agent_result.agent_id, "conversation_flow_id": flow_id}

        except Exception as e:
            logger.error(f"Failed to create agent from flow: {e}")
            return {"success": False, "error": str(e), "agent_id": None}
```

## Operation Type Decision Framework

| Operation Type        | Router Pattern  | Service Pattern            | When to Use                                    |
| --------------------- | --------------- | -------------------------- | ---------------------------------------------- |
| **Simple CRUD**       | Thin delegation | Single service method call | Single entity operations (list, get, delete)   |
| **Business Intent**   | Thin delegation | New orchestration method   | Multi-step workflows with business meaning     |
| **Atomic Multi-Step** | Thin delegation | Transaction orchestration  | Operations requiring all-or-nothing guarantees |
| **Complex Workflows** | Thin delegation | Dedicated workflow service | Multi-domain coordination with complex rules   |

**Golden Rules:**

- ✅ **Routers stay thin**: Always delegate to service methods, never contain business logic
- ✅ **Intent-driven methods**: Create new orchestration methods for business workflows
- ❌ **Don't chain CRUD**: Never chain basic service calls in routers
- ✅ **Compensation patterns**: Always handle external API failures with cleanup

## API Design Principles

**Prefer Atomic Operations Over Orchestration APIs:**

```python
# ❌ BAD: Orchestration API that couples multiple domains
@router.post("/complete-setup")
async def create_complete_setup(request: CompleteSetupRequest):
    """Single endpoint that creates multiple resources internally"""
    # Hidden orchestration - frontend has no visibility or control
    template = await template_service.create_template(request.template_data)
    flow = await flow_service.create_flow(template)
    agent = await agent_service.create_agent(flow)
    return CompleteSetupResponse(template=template, flow=flow, agent=agent)

# ✅ GOOD: Atomic APIs that do one thing well
@router.post("/templates")
async def create_template(request: TemplateRequest):
    """Creates only templates - single responsibility"""
    return await template_service.create_template(request)

@router.post("/flows")
async def create_flow(request: FlowRequest):
    """Creates only flows - single responsibility"""
    return await flow_service.create_flow(request)

@router.post("/agents")
async def create_agent(request: AgentRequest):
    """Creates only agents - single responsibility"""
    return await agent_service.create_agent(request)
```

**Why Atomic APIs Win:**

- ✅ **Composability**: Frontend can combine APIs in new ways without backend changes
- ✅ **Clear boundaries**: Each API has single responsibility
- ✅ **Independent testing**: Can test each operation separately
- ✅ **Better error handling**: Know exactly which step failed
- ✅ **Reusability**: APIs can be used by different features

**API Independence Rules:**

- Each endpoint should be independently useful
- APIs shouldn't assume specific usage patterns or sequences
- Avoid endpoints that exist only to coordinate other endpoints
- If your API only calls other internal APIs, question if it should exist

## Frontend vs Backend Orchestration Decision Framework

**Choose Frontend Orchestration When:**

- ✅ **Simple workflows**: 2-4 API calls with clear sequence
- ✅ **User-facing operations**: Users benefit from progress feedback
- ✅ **Partial failure scenarios**: Can retry individual steps or continue with partial success
- ✅ **Frequent UX changes**: Workflow presentation changes often
- ✅ **Different team ownership**: APIs are owned by different teams
- ✅ **No complex business rules**: Simple sequence without conditional logic

```javascript
// ✅ GOOD: Frontend orchestration with better UX
async function createCompleteSetup(config, setProgress) {
  setProgress('Creating template...');
  const template = await fetch('/api/templates', {
    method: 'POST',
    body: JSON.stringify(config.templateData),
  });

  if (!template.ok) {
    throw new Error(`Template creation failed: ${template.statusText}`);
  }

  setProgress('Creating flow...');
  const flow = await fetch('/api/flows', {
    method: 'POST',
    body: JSON.stringify({ template_id: template.id }),
  });

  setProgress('Creating agent...');
  const agent = await fetch('/api/agents', {
    method: 'POST',
    body: JSON.stringify({ flow_id: flow.id }),
  });

  setProgress('Complete!');
  return { template, flow, agent };
}
```

**Choose Backend Orchestration When:**

- ✅ **Complex transactions**: Operations must be atomic (all succeed or all fail)
- ✅ **Security-sensitive**: Operations should not be exposed to client manipulation
- ✅ **Background processing**: Long-running or scheduled operations
- ✅ **Complex business rules**: Conditional logic based on intermediate results
- ✅ **High-performance requirements**: Minimize client-server round trips
- ✅ **Stateful workflows**: Operations depend on previous state changes

```python
# ✅ GOOD: Backend orchestration for complex transactions
async def process_payment_and_provision_service(
    payment_data: dict,
    service_config: dict,
    db: AsyncSession
):
    """Complex transaction requiring atomicity"""
    async with db.begin():  # Database transaction
        # Business logic requiring database consistency
        payment = await payment_service.charge_customer(payment_data, db)
        if payment.status != "successful":
            raise PaymentFailedError("Payment was declined")

        # Conditional logic based on payment tier
        service_tier = determine_service_tier(payment.amount)

        # Multiple related database operations
        service = await service_provider.provision_service(service_tier, db)
        await notification_service.send_confirmation(payment, service, db)
        await audit_service.log_transaction(payment, service, db)

        return ProvisioningResult(payment=payment, service=service)
```

## Stello AI's Three-Layer Pattern Eliminates Common Anti-Patterns

**✅ What Works in Stello AI's Pattern:**

```python
# ✅ EXCELLENT: Thin routers that stay focused on HTTP concerns
@router.put("/voice-agent", response_model=schemas.VoiceAgentUpdateResponse)
async def update_voice_agent(request, current_user, org_context, db):
    """Router only handles HTTP - delegates immediately to service"""
    config_service = get_voice_agent_configuration_service()
    result = await config_service.update_voice_agent(request, org_context.organization_id, db)

    if not result["success"]:
        return schemas.VoiceAgentUpdateResponse(success=False, message=result.get("message"))

    return schemas.VoiceAgentUpdateResponse(success=True, message="Voice agent updated successfully")

# ✅ EXCELLENT: Main orchestrator coordinates specialized services
class VoiceAgentService:
    """Main orchestrator - stays within guardrails (~250 LOC, <8 operations)"""

    def __init__(self):
        # Composition of focused domain services
        self.creation_service = VoiceAgentCreationService()      # ~150 LOC, <5 ops
        self.configuration_service = VoiceAgentConfigurationService()  # ~200 LOC, <6 ops
        self.retrieval_service = VoiceAgentRetrievalService()    # ~100 LOC, <4 ops
        self.deletion_service = VoiceAgentDeletionService()      # ~120 LOC, <3 ops

    async def create_agent_for_organization(self, request, organization_id, db):
        """Orchestrates creation workflow - thin coordination only"""
        result = await self.create_agent_from_flow_id(
            flow_id=request.flow_id,
            agent_name=request.name,
            voice_id=request.voice_id,
            organization_id=organization_id,
            api_base_url="http://localhost:8001"
        )

        # Transform to response schema - orchestrator handles API contracts
        if not result.get("success"):
            return schemas.VoiceAgentCreateResponse(success=False, message=result.get("message"))

        return schemas.VoiceAgentCreateResponse(
            success=True,
            agent_id=result.get("agent_id"),
            conversation_flow_id=request.flow_id
        )

# ✅ EXCELLENT: Specialized service focuses on single domain
class VoiceAgentCreationService:
    """Pure creation service - no orchestration, just domain operations"""

    async def create_agent_from_flow_id(self, flow_id, agent_name, voice_id, organization_id, api_base_url):
        """Single responsibility: Create agent from existing flow"""
        agent_service = self._get_agent_service()

        try:
            response_engine = ResponseEngineResponseEngineConversationFlow(
                type="conversation-flow", conversation_flow_id=flow_id
            )
            webhook_url = f"{api_base_url}/api/v1/retell/webhook?organization_id={organization_id}"

            agent_result = await agent_service.create_agent(
                agent_name=agent_name, voice_id=voice_id, webhook_url=webhook_url, response_engine=response_engine
            )

            return {"success": True, "agent_id": agent_result.agent_id, "conversation_flow_id": flow_id}

        except Exception as e:
            logger.error(f"Failed to create agent from flow: {e}")
            return {"success": False, "error": str(e), "agent_id": None}
```

**Why This Pattern Works:**

1. **Clear Responsibilities**: Router (HTTP) → Orchestrator (coordination) → Domain Service (business logic)
2. **Service Guardrails**: Each service stays <500 LOC, <8 operations, single domain
3. **No Service-to-Service Calls**: Domain services never call each other directly
4. **Testability**: Each layer can be tested in isolation
5. **Maintainability**: Changes stay within clear boundaries

## The Orchestration Layer Anti-Pattern

**Red Flags of Unnecessary Orchestration Services:**

```python
# 🚨 RED FLAGS: Service that only coordinates other services
class SetupOrchestrator:
    """Warning: Service name contains 'Orchestrator' or 'Manager'"""

    def __init__(self):
        self.template_service = TemplateService()
        self.flow_service = FlowService()
        self.agent_service = AgentService()

    async def create_complete_setup(self, config: dict):
        """Warning: Method only calls other services"""
        # No business logic - just coordination
        template = await self.template_service.create(config.template)
        flow = await self.flow_service.create(template.id)
        agent = await self.agent_service.create(flow.id)
        return CompleteSetup(template, flow, agent)
```

**Questions to Ask:**

- **"Does this service only call other services?"** → Consider frontend orchestration
- **"What unique business value does this provide?"** → If none, eliminate it
- **"Could the client handle this coordination?"** → Often yes for user-facing workflows
- **"Are we creating this just to 'have orchestration'?"** → Avoid architectural cargo cult

**When Orchestration Services Make Sense:**

- Complex business rules between operations
- Database transactions spanning multiple services
- Background/async processing requirements
- Security isolation between operations

## Long-term Architecture Benefits

**Frontend Orchestration Advantages:**

**Team Velocity:**

- Frontend teams iterate on UX without backend deployment
- API teams develop services independently
- No coordination needed for simple workflow changes
- Faster feature delivery cycles

**Better User Experience:**

- Real-time progress indicators during multi-step operations
- Specific error messages for each step that failed
- Ability to retry individual failed steps
- Partial success scenarios (some operations succeeded)

**System Resilience:**

- Graceful degradation when some APIs are down
- Client-side retry logic for transient failures
- Easier debugging - clear which step failed
- No single point of failure for compound operations

**Maintenance Benefits:**

- Fewer backend services to maintain and deploy
- Clearer API boundaries and responsibilities
- Reduced coupling between backend services
- Simpler testing strategies

## Decision Framework Summary

**Start with Frontend Orchestration by Default for User-Facing Workflows**

Ask these questions to validate:

1. **Atomicity**: Do operations need database transaction guarantees?
2. **Security**: Should clients control the workflow sequence?
3. **Complexity**: Are there conditional business rules between steps?
4. **Performance**: Are round-trip costs prohibitive?

**If you answer "No" to most questions → Use frontend orchestration**
**If you answer "Yes" to multiple questions → Use backend orchestration**

**Golden Rule**: Don't create backend orchestration layers just because you can. Create them because you must.

## Frontend Organization Context Pattern (Explicit Pattern)

**Stello AI uses explicit organization context passing via service methods - clear, traceable, and maintainable.**

### Pattern Overview

Every service that needs organization context follows the same explicit pattern:

```typescript
// Services have organizationId property
class RetellService {
  constructor(private organizationId?: string) {}

  setOrganizationId(orgId: string) {
    this.organizationId = orgId;
  }

  async getCalls() {
    return ApiClient.get('/retell/calls', {
      organizationId: this.organizationId  // ← Explicit passing
    });
  }
}

// Hooks set organization context on services
export const useCalls = () => {
  const { organization } = useAuth();

  useEffect(() => {
    if (organization?.id) {
      retellService.setOrganizationId(organization.id);
    }
  }, [organization?.id]);

  return useQuery({
    queryKey: ['calls', organization?.id],  // ← Include org in cache key
    queryFn: () => retellService.getCalls(),
    enabled: !!organization?.id,
  });
};
```

### Why This Pattern

**Explicit > Implicit:**
- ✅ Clear data flow: Hook → Service → ApiClient → Backend
- ✅ Easy to trace and debug
- ✅ No hidden dependencies or global state
- ✅ Testable: Services are pure, no magic context lookup
- ✅ Type-safe: Organization ID explicitly passed

**React Query Cache Keys Matter:**

Organization ID in cache keys is CRITICAL for multi-tenant apps:
```typescript
// WITHOUT org ID in cache key (WRONG)
queryKey: ['calls']
// User switches Org A → Org B
// React Query returns cached Org A data (BUG!)

// WITH org ID in cache key (CORRECT)
queryKey: ['calls', 'org-b-id']
// User switches Org A → Org B
// Cache key changes, React Query refetches (CORRECT!)
```

### Service Pattern Template

Apply this pattern to all services:

```typescript
class SomeService {
  constructor(private organizationId?: string) {}

  setOrganizationId(orgId: string) {
    this.organizationId = orgId;
  }

  async getData() {
    return ApiClient.get('/endpoint', {
      organizationId: this.organizationId
    });
  }
}

// Export singleton instance
export const someService = new SomeService();
```

### Hook Pattern Template

Apply this pattern to all hooks:

```typescript
export const useData = () => {
  const { organization } = useAuth();

  // Set org ID on service
  useEffect(() => {
    if (organization?.id) {
      someService.setOrganizationId(organization.id);
    }
  }, [organization?.id]);

  return useQuery({
    queryKey: ['data', organization?.id],  // Include org ID
    queryFn: () => someService.getData(),
    enabled: !!organization?.id,           // Only run with org
  });
};
```

### Benefits of This Pattern

| Aspect | Benefit |
| --- | --- |
| **Traceability** | Clear data flow from hook → service → API |
| **Testability** | Services are pure functions, easy to mock |
| **Maintainability** | No hidden dependencies or global state |
| **Debugging** | Stack traces show exact data flow |
| **Scalability** | Proven pattern scales to 20+ service methods |
| **Type Safety** | Organization ID type-checked at each step |

### Real-World Example: Voice Agents

This is how the RetellService actually works in production:

```typescript
class RetellService {
  constructor(private organizationId?: string) {}

  setOrganizationId(orgId: string) {
    this.organizationId = orgId;
  }

  async getVoiceAgents() {
    return ApiClient.get<RetellVoiceAgentInfo[]>('/retell/voice-agents', {
      organizationId: this.organizationId
    });
  }

  // ... 20+ more methods using same pattern
}

// In hooks:
export const useVoiceAgents = () => {
  const { organization } = useAuth();

  useEffect(() => {
    retellService.setOrganizationId(organization?.id || '');
  }, [organization?.id]);

  return useQuery({
    queryKey: [VOICE_AGENT_QUERY_KEY, organization?.id],
    queryFn: () => retellService.getVoiceAgents(),
    enabled: !!organization?.id,
  });
};
```

---

## Pydantic Schema Design Patterns

**All API schemas should inherit from `BaseSchema` for consistent JSON serialization:**

```python
from app.schemas.base import BaseSchema

class UserResponse(BaseSchema):
    id: UUID
    email: str
    first_name: str  # Will become firstName in JSON
    created_at: datetime  # Will become createdAt in JSON
```

### Field Naming Convention

- **Python models**: Use `snake_case` for all field names
- **JSON/API**: Automatic conversion to `camelCase` via `alias_generator=to_camel`
- **Frontend**: Use `camelCase` to match API responses

```python
# ✅ CORRECT: Python uses snake_case
class OrganizationResponse(BaseSchema):
    organization_id: UUID
    created_at: datetime
    is_active: bool

# JSON output: {"organizationId": "...", "createdAt": "...", "isActive": true}
```

### Required vs Optional Fields in Pydantic Models

**Critical Pattern**: How you define Pydantic fields affects OpenAPI schema generation and TypeScript types.

#### ✅ CORRECT: Required Fields Without Defaults

```python
class MyResponse(BaseModel):
    # These fields are REQUIRED in OpenAPI/TypeScript
    organizations: list[OrganizationItem]  # No default = required
    permissions: list[str]  # No default = required
    features: dict[str, bool]  # No default = required
```

#### ❌ INCORRECT: Using default_factory Makes Fields Optional

```python
class MyResponse(BaseModel):
    # These become OPTIONAL in OpenAPI/TypeScript!
    organizations: list[OrganizationItem] = Field(default_factory=list)  # Optional!
    permissions: list[str] = Field(default_factory=list)  # Optional!
    features: dict[str, bool] = Field(default_factory=dict)  # Optional!
```

#### When to Use default_factory

Only use `default_factory` when the field should be **truly optional** with a default value:

```python
class UserPreferences(BaseModel):
    # Optional field that defaults to empty list if not provided
    ignored_notifications: list[str] = Field(default_factory=list)
```

#### Best Practices

1. **Required fields**: Don't provide any default value
2. **Optional fields with None default**: Use `field: Type | None = None`
3. **Optional fields with non-None default**: Use `Field(default=value)` or `Field(default_factory=func)`
4. **Always initialize empty collections** in your service layer, not in the model

#### Example: Session Response Pattern

```python
# Backend: Initialize empty collections in service
permissions = []  # Initialize in service
features = {}  # Initialize in service

return SessionResponse(
    user=user_data,
    permissions=permissions,  # Pass empty list explicitly
    features=features,  # Pass empty dict explicitly
)
```

This ensures TypeScript gets the correct types without manual overrides!

### Frontend/Backend Type Integration

Follow this workflow for type safety:

1. **Backend**: Update Pydantic schemas
2. **Export**: Run `make export-schema` to generate OpenAPI spec
3. **Generate**: Run `make generate-types` to create TypeScript types
4. **Frontend**: Import from `@stello/shared-types`

## Data Layer Architecture: Models vs Schemas

Understanding the distinction between models and schemas is critical for clean architecture and avoiding common mistakes.

### The Fundamental Distinction

**Models** (`models.py`):

- SQLAlchemy ORM models representing database tables
- Define database schema, relationships, constraints, indexes
- Located in `app/features/*/models.py` or `app/models/` (shared)
- Represent the **persistent data structure**
- Example: `class EventType(Base)` with database columns

**Schemas** (`schemas.py`):

- Pydantic models for API request/response validation and transformation
- Define data shape for network communication and validation rules
- Located appropriately based on purpose (see placement rules below)
- Represent the **communication data structure**
- Example: `class CreateEventTypeRequest(BaseSchema)`

### Schema Placement Rules

**Internal API Schemas** → `app/features/[feature]/schemas.py`

```python
# app/features/calendar/schemas.py
class CreateEventTypeRequest(BaseSchema):
    """Our internal API request format"""
    title: str
    duration_minutes: int  # Our domain field name
    custom_name: str | None
```

**External API Schemas** → `app/integrations/[service]/schemas.py`

```python
# app/integrations/cal_com/schemas.py
class CalComEventTypePayload(CalComBaseSchema):
    """External API schema matching their exact format"""
    title: str
    length: int  # Their field name, not ours
    customName: str | None  # Their camelCase format
```

**Shared Base Schemas** → `app/schemas/base.py`

```python
# app/schemas/base.py
class BaseSchema(BaseModel):
    """Base for all internal schemas"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        # ... standard configuration
    )
```

### External API Integration Pattern

For external services (Cal.com, Stripe, Retell, etc.), use Pydantic schemas with transformation methods:

```python
# app/integrations/cal_com/schemas.py
class CalComEventTypePayload(CalComBaseSchema):
    """Cal.com API schema with transformation logic"""

    # Fields matching Cal.com's API exactly
    title: str
    length: int  # Cal.com uses 'length', we use 'duration_minutes'
    customName: str | None
    destinationCalendar: CalComDestinationCalendar | None
    minimumBookingNotice: int

    @classmethod
    def from_domain(cls, request: CreateEventTypeRequest) -> "CalComEventTypePayload":
        """Transform our domain model to Cal.com's API format"""
        # Apply field mappings and business rules
        custom_name = request.custom_name
        if not custom_name:
            custom_name = "{Event type title} between {Organizer} and {Scheduler}"

        return cls(
            title=request.title,
            length=request.duration_minutes,  # Field name mapping
            customName=custom_name,
            minimumBookingNotice=request.minimum_booking_notice,
            # ... handle all field transformations
        )

    def to_api_dict(self) -> dict[str, Any]:
        """Get dictionary ready for API call"""
        return self.model_dump(by_alias=True, exclude_none=True)
```

### Decision Matrix: Transformation Patterns

| Scenario                   | Pattern                 | Location                    | Example                                    |
| -------------------------- | ----------------------- | --------------------------- | ------------------------------------------ |
| **Simple field mapping**   | Pydantic factory method | `integrations/*/schemas.py` | `CalComEventTypePayload.from_domain()`     |
| **Complex business logic** | Service method          | `features/*/service.py`     | Multi-step transformations with validation |
| **Direct SDK usage**       | SDK types directly      | Import directly             | `from stripe import Customer`              |
| **Manual dict building**   | **AVOID**               | -                           | Legacy pattern, refactor when touched      |

### Benefits of This Architecture

1. **Single Source of Truth**: External API structure defined in one place
2. **Type Safety**: Pydantic validation for all API boundaries
3. **Maintainability**: When external APIs change, update one schema file
4. **Clear Separation**: Our domain vs external system domain
5. **Testability**: Transformation logic can be unit tested independently

### Common Anti-Patterns to Avoid

❌ **Bypassing transformation schemas**:

```python
# Service manually building external API payload
cal_com_data = {
    "title": title,
    "customName": custom_name,  # Manual dict building
    "length": duration_minutes,
}
```

✅ **Using transformation schemas**:

```python
# Clean transformation using schema
payload = CalComEventTypePayload.from_domain(request)
cal_com_data = payload.to_api_dict()
```

❌ **Mixing external API format in internal schemas**:

```python
# Internal schema using external field names
class CreateEventTypeRequest(BaseSchema):
    length: int  # Wrong! This is Cal.com's field name
```

✅ **Keeping domain language in internal schemas**:

```python
# Internal schema uses our domain language
class CreateEventTypeRequest(BaseSchema):
    duration_minutes: int  # Correct! Our domain field name
```

```typescript
import type {
  SessionResponse,
  OnboardingStatusResponse,
} from '@stello/shared-types';
```

Ensure frontend code uses camelCase to match API responses:

```typescript
// ✅ CORRECT: Frontend matches API camelCase
const existingConfig = onboardingStatus?.existingConfig || null;
const currentStep = onboardingStatus?.currentStep;

// ❌ INCORRECT: Mismatched field names
const existingConfig = onboardingStatus?.existing_config || null; // Wrong!
const currentStep = onboardingStatus?.current_step; // Wrong!
```

## Webhook Validation Patterns

Webhooks require special handling due to their external origin and multiple payload types. Follow the **Parse, Don't Validate** principle at webhook entry points.

### ✅ Discriminated Union Pattern (Recommended)

**Use this pattern for webhooks with multiple types** - provides type safety, performance, and clear error messages.

```python
# app/features/retell/webhooks/schemas.py
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class RetellCallMetadata(BaseModel):
    """Shared call context across all webhook types"""
    call_id: str
    agent_id: str
    call_status: str

class CheckAvailabilityCall(BaseModel):
    """Type-safe availability check webhook"""
    name: Literal["check_appointment_availability"]
    call: RetellCallMetadata
    args: CheckAvailabilityParams  # Typed, not dict!

class BookAppointmentCall(BaseModel):
    """Type-safe booking webhook"""
    name: Literal["book_appointment"]
    call: RetellCallMetadata
    args: BookAppointmentParams  # Typed, not dict!

# Discriminated union - Pydantic picks correct type based on "name" field
RetellFunctionCall = Annotated[
    Union[CheckAvailabilityCall, BookAppointmentCall],
    Field(discriminator="name")
]
```

```python
# app/features/retell/webhooks/router.py
from pydantic import parse_obj_as, ValidationError

async def handle_webhook(data: dict) -> dict:
    """Single validation point - fail fast with clear errors"""
    try:
        # Parse once, typed everywhere
        function_call = parse_obj_as(RetellFunctionCall, data)

        # Now fully type-safe throughout the codebase!
        if isinstance(function_call, CheckAvailabilityCall):
            # function_call.args is CheckAvailabilityParams
            return await handler.check_availability(function_call.args, ...)
        elif isinstance(function_call, BookAppointmentCall):
            # function_call.args is BookAppointmentParams
            return await handler.book_appointment(function_call.args, ...)

    except ValidationError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return {"success": False, "error": e.errors()}
```

### ✅ Fallback Pattern for Resilience

**Add graceful handling for unknown webhook types** using `union_mode="left_to_right"`:

```python
# Known webhook types with validation
KnownWebhooks = Annotated[
    Union[CheckAvailabilityCall, BookAppointmentCall],
    Field(discriminator="name")
]

# Generic fallback for unknown types
class UnknownWebhook(BaseModel):
    """Fallback for new webhook types we haven't implemented yet"""
    name: str
    call: dict  # Flexible structure
    args: dict  # Preserve unknown data

# Resilient union - try known types first, fallback to generic
WebhookPayload = Annotated[
    Union[KnownWebhooks, UnknownWebhook],
    Field(union_mode="left_to_right")
]
```

### ❌ Anti-Pattern: Loose Dict Validation

**Don't do this** - leads to runtime errors and poor type safety:

```python
# ❌ WRONG: Loose validation with dicts
async def handle_webhook(data: dict) -> dict:
    function_name = data.get("name")  # Could be None!
    args = data.get("args", {})       # Untyped dict - no validation

    if function_name == "book_appointment":
        # Validation happens later - error-prone
        try:
            params = BookingParams(**args)  # Could fail here
        except ValidationError:
            # Now what? Data already partially processed
            pass

    # No IDE support, no type safety, scattered validation
```

### Recommended Directory Structure

```
webhooks/
├── schemas.py       # All webhook Pydantic models
├── router.py        # HTTP layer with discriminated union validation
└── handlers/        # Provider-specific business logic
    ├── stripe_handler.py
    └── retell_handler.py
```

### Key Benefits

1. **Type Safety**: IDE autocomplete and compile-time type checking
2. **Performance**: Discriminated unions are faster than plain unions
3. **Documentation**: Self-documenting webhook structure
4. **Error Clarity**: Pydantic provides structured validation errors
5. **Resilience**: Fallback pattern handles unknown types gracefully
6. **Single Validation**: Parse once, use typed objects throughout

### Testing Webhook Schemas

```python
def test_webhook_validation():
    """Test discriminated union validation"""
    # Valid booking webhook
    valid_payload = {
        "name": "book_appointment",
        "call": {"call_id": "123", "agent_id": "456", "call_status": "active"},
        "args": {"event_type_id": "789", "start_time": "2024-01-15T14:00:00Z", ...}
    }

    webhook = parse_obj_as(RetellFunctionCall, valid_payload)
    assert isinstance(webhook, BookAppointmentCall)
    assert webhook.args.event_type_id == "789"

    # Invalid webhook should raise ValidationError
    invalid_payload = {"name": "unknown_function", "invalid": "structure"}
    with pytest.raises(ValidationError):
        parse_obj_as(RetellFunctionCall, invalid_payload)
```

## Webhook Response Patterns vs REST API Patterns

**Critical distinction**: Webhooks and REST APIs use completely different error handling patterns. Confusing these leads to broken integrations.

### The Key Difference

**REST APIs** use HTTP status codes to indicate operation results:

```python
# ✅ REST API - Use HTTP status codes
@router.get("/organizations/{org_id}")
async def get_organization(org_id: str):
    organization = await db.get(Organization, org_id)
    if not organization:
        raise HTTPException(404, "Organization not found")  # Correct!
    return organization

# Test expects proper status codes
assert response.status_code == 404
assert response.json()["detail"] == "Organization not found"
```

**Webhooks** must return 200-299 for acknowledgment, regardless of business logic outcomes:

```python
# ✅ Webhook Handler - Always return 200 with error in body
@router.post("/retell/webhook")
async def handle_retell_webhook(data: dict):
    if not organization:
        # MUST return 200 - tells Retell "webhook received successfully"
        return {"success": False, "error": "organization_not_found"}

    # Business logic success/failure goes in response body
    return {"success": True, "data": result}

# Test expects 200 with error in body
assert response.status_code == 200
assert response.json()["success"] is False
assert response.json()["error"] == "organization_not_found"
```

### Why Webhooks Work Differently

**Industry Standard Practice** ([Stripe](https://docs.stripe.com/webhooks), [GitHub](https://docs.github.com/webhooks), [Slack](https://api.slack.com/events-api)):

1. **Acknowledgment vs Processing**: HTTP status indicates delivery success, not business logic success
2. **Retry Logic**: Non-2xx responses trigger automatic retries by the webhook sender
3. **Timeout Constraints**: Must respond within 3-10 seconds or webhook is marked failed

### Common Examples from Major Providers

**Stripe Documentation**:

> "You should return a 200 to Stripe, even when encountering application errors. Otherwise, Stripe will continue to retry sending the event to your endpoint."

**Slack Events API**:

> "Respond with 200 OK within 3 seconds and process the event asynchronously."

**GitHub Webhooks**:

> "Your server should respond with a 2xx response to indicate successful delivery receipt."

### The Two-Phase Pattern

**Phase 1: Acknowledge Receipt (Immediate)**

```python
@router.post("/webhook")
async def webhook_handler(payload: dict):
    # Phase 1: Immediate acknowledgment (< 3 seconds)
    await queue_for_processing(payload)  # Store for later
    return {"received": True}  # 200 OK - webhook delivered successfully

# Phase 2: Process Asynchronously (Background)
async def process_webhook_background(payload: dict):
    try:
        # Your business logic here - can take as long as needed
        await complex_business_operation(payload)
    except Exception as e:
        # Handle errors in your own system - Webhook sender is out of the loop
        await log_error_and_retry_later(e)
```

### Anti-Pattern: Using REST Status Codes in Webhooks

```python
# ❌ WRONG: This breaks webhook retry logic
@router.post("/webhook")
async def bad_webhook_handler(data: dict):
    if not organization:
        # This tells the sender "webhook endpoint failed" not "organization not found"
        raise HTTPException(404, "Organization not found")  # Will cause infinite retries!

    if invalid_data:
        # Sender will retry this forever
        raise HTTPException(400, "Invalid data")  # Wrong pattern for webhooks!
```

**Why this breaks**:

- Webhook sender interprets 404 as "endpoint doesn't exist" → retries indefinitely
- 400/500 status codes trigger retry logic when you want them to stop
- Sender has no way to distinguish endpoint errors from business logic errors

### When to Use Each Pattern

| Use Case                           | Pattern           | Status Code                           | Error Location |
| ---------------------------------- | ----------------- | ------------------------------------- | -------------- |
| **REST API** - Get user            | HTTP status codes | `404`                                 | HTTP response  |
| **REST API** - Create resource     | HTTP status codes | `201` success, `400` validation error | HTTP response  |
| **Webhook** - Process payment      | Always 200        | `200`                                 | Response body  |
| **Webhook** - Function call result | Always 200        | `200`                                 | Response body  |

### Stello's Current Implementation

Your webhook handlers correctly follow industry standards:

```python
# ✅ This is correct and follows best practices
return {
    "success": False,
    "error": "organization_not_found",
    "message": "Organization not found for this request"
}
```

While Retell accepts any response format, the structured approach provides:

- **Consistency** across all webhook responses
- **Debuggability** with clear error categorization
- **AI Comprehension** - structured data helps Retell's LLM understand results

### Testing Webhook vs REST Patterns

```python
# REST API Test - Check status codes
def test_rest_api_not_found():
    response = client.get("/api/organizations/nonexistent")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

# Webhook Test - Always expect 200 with error in body
def test_webhook_organization_error():
    response = client.post("/webhook", json=webhook_payload)
    assert response.status_code == 200  # Webhook acknowledged
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "organization_not_found"
```

### Key Takeaway

**Never use `raise HTTPException()` in webhook handlers.** Always return 200 with structured response body. Save HTTP status codes for REST APIs where they belong.

## Related Guides

- [Service Architecture](service-architecture.md) - How to design the services that power these APIs
- [Integration Patterns](integration-patterns.md) - How to handle external API calls in these patterns
- [Decision Frameworks](decision-frameworks.md) - Decision matrices for API orchestration choices
