# Anti-Patterns & Common Mistakes

This guide identifies common anti-patterns, mistakes to avoid, and red flags that indicate architectural problems.

## Service Architecture Anti-Patterns

### Over-Layering Services

**❌ BAD: Multiple layers for single domain**

```python
# DON'T: Unnecessary complexity for simple operations
class TemplateRepository:  # Database layer
    async def save_template(self, template): ...

class TemplateBusinessService:  # Business layer
    def __init__(self):
        self.repository = TemplateRepository()

    async def validate_and_save(self, template):
        # Just calls repository
        return await self.repository.save_template(template)

class TemplateOrchestrator:  # Orchestration layer
    def __init__(self):
        self.business_service = TemplateBusinessService()

    async def create_template(self, data):
        # Just calls business service
        return await self.business_service.validate_and_save(data)
```

**✅ GOOD: Single service for single domain**

```python
# DO: One focused service with private helpers
class TemplateService:
    async def create_template(self, data):
        validated = self._validate_template(data)
        return await self._save_template(validated)

    def _validate_template(self, data): ...  # Private helper
    async def _save_template(self, data): ...  # Private helper
```

### Service-to-Service Calls

**❌ BAD: Services calling other services directly**

```python
# DON'T: Creates tight coupling and circular dependencies
class FlowService:
    def __init__(self):
        self.agent_service = AgentService()  # Direct dependency

    async def create_flow_with_agent(self, config):
        flow = await self._create_flow(config.flow_data)
        # Service calling another service directly
        agent = await self.agent_service.create_agent(config.agent_data)
        return CompleteSetup(flow, agent)

class AgentService:
    def __init__(self):
        self.flow_service = FlowService()  # Circular dependency!

    async def create_agent_with_flow(self, config):
        # Creates circular dependency
        flow = await self.flow_service.create_flow(config.flow_data)
        agent = await self._create_agent(config.agent_data)
        return CompleteSetup(flow, agent)
```

**✅ GOOD: Orchestrator coordinates services**

```python
# DO: Let orchestrator handle coordination
class RetellService:  # Main orchestrator
    def __init__(self):
        self.flow_service = FlowService()      # Clean dependencies
        self.agent_service = AgentService()    # No circular references

    async def create_complete_setup(self, config):
        flow = await self.flow_service.create_flow(config.flow_data)
        agent = await self.agent_service.create_agent(config.agent_data)
        return CompleteSetup(flow, agent)

# Services stay focused and independent
class FlowService:
    async def create_flow(self, data): ...  # No dependencies on other services

class AgentService:
    async def create_agent(self, data): ...  # No dependencies on other services
```

### Fat Service Classes

**❌ BAD: Service exceeds guardrails**

```python
# DON'T: Exceeds 500 LOC and 8 operations
class MegaTemplateService:  # 800+ LOC, 12+ operations
    # Handles templates, agents, flows, analytics - multiple domains

    async def load_template(self): ...           # Template domain
    async def customize_template(self): ...      # Template domain
    async def create_agent(self): ...            # Agent domain
    async def setup_analytics(self): ...         # Analytics domain
    async def create_flow(self): ...             # Flow domain
    async def send_notifications(self): ...      # Notification domain
    async def backup_data(self): ...             # Backup domain
    async def generate_reports(self): ...        # Reporting domain
    async def manage_users(self): ...            # User domain
    async def handle_payments(self): ...         # Payment domain
    async def configure_webhooks(self): ...      # Webhook domain
    async def sync_external_data(self): ...      # Integration domain
```

**✅ GOOD: Focused services within guardrails**

```python
# DO: Split by business domain, stay within limits
class TemplateService:  # ~200 LOC, 4 operations, single domain
    async def load_template(self): ...
    async def customize_template(self): ...
    async def validate_template(self): ...
    async def save_template(self): ...

class AgentService:  # ~250 LOC, 5 operations, single domain
    async def create_agent(self): ...
    async def update_agent(self): ...
    async def delete_agent(self): ...
    async def list_agents(self): ...
    async def configure_agent(self): ...
```

## Directory Organization Anti-Patterns

### False Domains

**❌ BAD: Folders that are just orchestration**

```python
# DON'T: Create folders for workflows instead of domains
app/features/retell/
├── agent_setup/              # 🚩 FALSE DOMAIN: Just orchestration
│   ├── service.py           # Only coordinates other services
│   ├── outbound_service.py  # Specialized workflow
│   └── admin_router.py      # Admin endpoints
├── user_onboarding/          # 🚩 FALSE DOMAIN: Just a workflow
├── payment_processing/       # 🚩 FALSE DOMAIN: Just a workflow
├── conversation_flows/       # ✅ True domain
├── voice_agents/             # ✅ True domain
```

**✅ GOOD: True business domains**

```python
# DO: Organize by business entities, not workflows
app/features/retell/
├── service.py                # Main orchestrator handles workflows
├── conversation_flows/       # True domain: manages conversation flows
├── voice_agents/             # True domain: manages voice agents
└── router.py                 # API endpoints
```

### Global Model Dumping Ground

**❌ BAD: All models in one place**

```python
# DON'T: Everything in global models directory
app/
├── models/              # 50+ model files mixed together
│   ├── user.py         # Used by many features
│   ├── organization.py # Used by many features
│   ├── retell.py       # Only used by retell feature
│   ├── appointment.py  # Only used by appointments feature
│   ├── calendar.py     # Only used by appointments feature
│   ├── webhook.py      # Only used by webhooks feature
│   ├── analytics.py    # Only used by analytics feature
│   └── ... (45 more files)
└── features/
    ├── retell/         # Depends on global models
    └── appointments/   # Depends on global models
```

**✅ GOOD: Strategic model placement**

```python
# DO: Shared models global, feature-specific models colocated
app/
├── models/              # Only truly shared models
│   ├── user.py         # Used by 3+ features
│   ├── organization.py # Used by 3+ features
│   └── base.py         # Base classes and mixins
└── features/
    ├── retell/
    │   ├── models.py   # RetellConfiguration, etc.
    │   └── service.py
    └── appointments/
        ├── models.py   # Appointment, Schedule, etc.
        └── service.py
```

## API Design Anti-Patterns

### Orchestration APIs That Couple Domains

**❌ BAD: Single endpoint that creates multiple resources**

```python
# DON'T: Hidden orchestration coupling multiple domains
@router.post("/complete-setup")
async def create_complete_setup(request: CompleteSetupRequest):
    """Single endpoint that hides complexity"""
    # Hidden orchestration - frontend has no control
    template = await template_service.create_template(request.template_data)
    flow = await flow_service.create_flow(template)
    agent = await agent_service.create_agent(flow)
    phone = await phone_service.assign_number(agent)
    return CompleteSetupResponse(template=template, flow=flow, agent=agent, phone=phone)
```

**✅ GOOD: Atomic APIs that compose**

```python
# DO: Independent APIs that can be composed
@router.post("/templates")
async def create_template(request: TemplateRequest):
    return await template_service.create_template(request)

@router.post("/flows")
async def create_flow(request: FlowRequest):
    return await flow_service.create_flow(request)

@router.post("/agents")
async def create_agent(request: AgentRequest):
    return await agent_service.create_agent(request)
```

### Redundant Existence Checks

**❌ BAD: Making unnecessary API calls just to check existence**

```python
# DON'T: Extra API call that provides no value
async def cancel_event(self, event_id: str):
    # Pointless check - not using the return value
    try:
        await client.get_event(event_id)  # Waste of an API call
    except NotFoundError:
        return "Event not found"

    # The update will fail with the same error if event doesn't exist
    await client.update_event(event_id, {"status": "cancelled"})
```

**✅ GOOD: Let the operation itself handle validation**

```python
# DO: Single API call with proper error handling
async def cancel_event(self, event_id: str):
    try:
        await client.update_event(event_id, {"status": "cancelled"})
    except NotFoundError:
        return "Event not found"
```

**Why this is an anti-pattern:**

- **Wastes API calls**: Doubles the number of requests for no benefit
- **No value added**: The return value isn't used
- **Same error handling**: The actual operation fails with the same error
- **Performance impact**: Extra network latency and API quota usage
- **Code bloat**: Unnecessary complexity that adds no safety

**Rule**: If you're not using the return value and the next operation would fail with the same error anyway, remove the redundant check.

### Fat Routers with Business Logic

**❌ BAD: Business logic in routers**

```python
# DON'T: Business logic in router layer
@router.post("/agents")
async def create_agent(request: AgentRequest, db: DatabaseDep):
    # Business logic in router - WRONG LAYER!
    if not request.name or len(request.name) < 3:
        raise HTTPException(400, "Name must be at least 3 characters")

    # Complex business logic in router
    template = await db.execute(select(Template).where(Template.id == request.template_id))
    if not template:
        raise HTTPException(404, "Template not found")

    # Orchestration in router
    flow = await retell_client.create_flow(template.data)
    agent = await retell_client.create_agent(flow.id, request.name)

    # Database operations in router
    config = RetellConfiguration(agent_id=agent.id, flow_id=flow.id)
    db.add(config)
    await db.commit()

    return AgentResponse(agent_id=agent.id)
```

**✅ GOOD: Thin router delegation**

```python
# DO: Router only handles HTTP concerns
@router.post("/agents")
async def create_agent(request: AgentRequest, org_context: OrganizationContextDep, db: DatabaseDep):
    """Thin delegation to service layer"""
    service = get_voice_agent_service()
    return await service.create_agent_for_organization(request, org_context.organization_id, db)
```

### Unnecessary Orchestration Services

**❌ BAD: Service that only calls other services**

```python
# DON'T: Service that provides no unique value
class SetupOrchestrator:
    """Service that only coordinates - no business value"""

    def __init__(self):
        self.template_service = TemplateService()
        self.flow_service = FlowService()
        self.agent_service = AgentService()

    async def create_complete_setup(self, config):
        """Just calls other services - no business logic"""
        template = await self.template_service.create(config.template)
        flow = await self.flow_service.create(template.id)
        agent = await self.agent_service.create(flow.id)
        return CompleteSetup(template, flow, agent)
```

**✅ GOOD: Frontend orchestration for simple workflows**

```javascript
// DO: Let frontend handle simple coordination
async function createCompleteSetup(config, setProgress) {
  setProgress('Creating template...');
  const template = await api.createTemplate(config.template);

  setProgress('Creating flow...');
  const flow = await api.createFlow({ template_id: template.id });

  setProgress('Creating agent...');
  const agent = await api.createAgent({ flow_id: flow.id });

  setProgress('Complete!');
  return { template, flow, agent };
}
```

## Integration Anti-Patterns

### Premature Abstraction with Ports

**❌ BAD: Unnecessary abstraction for single vendor**

```python
# DON'T: Over-engineering with ports pattern
from abc import ABC, abstractmethod

class VoiceAgentPort(ABC):  # Unnecessary abstraction
    @abstractmethod
    async def create_agent(self, config: dict) -> dict: ...

class RetellAdapter(VoiceAgentPort):  # Only implementation
    async def create_agent(self, config: dict) -> dict:
        return await self.client.create_agent(config)

# Complex dependency injection for no benefit
class VoiceAgentService:
    def __init__(self, voice_port: VoiceAgentPort):
        self.voice_client = voice_port  # Unnecessary indirection
```

**✅ GOOD: Simple wrapper for single vendor**

```python
# DO: Direct wrapper when you have one vendor
class RetellClient:
    async def create_agent(self, config: dict) -> dict:
        try:
            result = await self.client.agent.create(**config)
            return {"agent_id": result.agent_id}
        except RetellError as e:
            raise ExternalServiceError(f"Failed to create agent: {e}")

class VoiceAgentService:
    def __init__(self):
        self.retell = RetellClient()  # Simple, direct
```

### Business Logic in Integration Layer

**❌ BAD: Business rules in integration clients**

```python
# DON'T: Business logic in integration layer
class RetellClient:
    async def create_production_agent(self, config: dict) -> dict:
        # WRONG: Business logic in integration layer
        if config.get("environment") == "production":
            config["backup_enabled"] = True
            config["monitoring_level"] = "comprehensive"
            config["retry_attempts"] = 5

        # WRONG: Validation in integration layer
        if not config.get("organization_id"):
            raise ValueError("Organization ID required for production agents")

        # WRONG: Database operations in integration layer
        existing = await self.db.get_agent_by_name(config["name"])
        if existing:
            raise ValueError("Agent name already exists")

        return await self.client.agent.create(**config)
```

**✅ GOOD: Thin wrapper with no business logic**

```python
# DO: Keep integration layer thin
class RetellClient:
    async def create_agent(self, config: dict) -> dict:
        """Thin wrapper - only error handling and logging"""
        try:
            result = await self.client.agent.create(**config)
            logger.info(f"Created agent: {result.agent_id}")
            return {"agent_id": result.agent_id}
        except RetellError as e:
            logger.error(f"Retell API error: {e}")
            raise ExternalServiceError(f"Failed to create agent: {e}")

# Business logic stays in service layer
class VoiceAgentService:
    async def create_production_agent(self, config: dict) -> dict:
        # Business rules in correct layer
        production_config = self._apply_production_settings(config)
        self._validate_production_requirements(production_config)
        await self._check_name_availability(production_config["name"])

        return await self.retell.create_agent(production_config)
```

### Circular Dependencies in Integrations

**❌ BAD: Integration importing from features**

```python
# DON'T: Creates circular dependency
# app/integrations/retell/client.py
from app.features.voice_agents.models import VoiceAgent  # WRONG!

class RetellClient:
    async def create_agent(self, config: dict) -> VoiceAgent:
        result = await self.client.agent.create(**config)
        # Integration layer creating business models - WRONG!
        return VoiceAgent(
            agent_id=result.agent_id,
            name=result.name,
            organization_id=config["organization_id"]
        )
```

**✅ GOOD: One-way dependency flow**

```python
# DO: Integration returns simple data
# app/integrations/retell/client.py
class RetellClient:
    async def create_agent(self, config: dict) -> dict:
        result = await self.client.agent.create(**config)
        # Return simple data, no business models
        return {
            "agent_id": result.agent_id,
            "name": result.name
        }

# Feature layer handles business models
# app/features/voice_agents/service.py
from app.integrations.retell.client import RetellClient

class VoiceAgentService:
    async def create_agent(self, config: dict) -> VoiceAgent:
        result = await self.retell.create_agent(config)
        # Service layer creates business models
        return VoiceAgent(
            agent_id=result["agent_id"],
            name=result["name"],
            organization_id=config["organization_id"]
        )
```

## Schema Design Anti-Patterns

### Double CamelCase Bug

**❌ BAD: Using both alias_generator and explicit Field aliases**

```python
# DON'T: Double conversion (snake_case → camelCase → CamelCase)
class BuggySchema(BaseSchema):
    created_at: datetime = Field(alias="createdAt")  # WRONG!
    # Results in: "CreatedAt" in JSON (double conversion)
```

**✅ GOOD: Let alias_generator handle conversion**

```python
# DO: Automatic conversion via alias_generator
class CorrectSchema(BaseSchema):
    created_at: datetime  # Becomes "createdAt" automatically
```

### Optional Fields with default_factory

**❌ BAD: Making required fields optional in TypeScript**

```python
# DON'T: default_factory makes fields optional in TypeScript
class SessionResponse(BaseSchema):
    permissions: list[str] = Field(default_factory=list)  # Optional in TS!
    features: dict[str, bool] = Field(default_factory=dict)  # Optional in TS!
```

**✅ GOOD: Required fields with no defaults**

```python
# DO: Required fields for TypeScript type safety
class SessionResponse(BaseSchema):
    permissions: list[str]   # Required in TypeScript
    features: dict[str, bool] # Required in TypeScript

# Initialize in service layer instead
def get_session_data(user: User) -> SessionResponse:
    return SessionResponse(
        permissions=[],  # Initialize explicitly
        features={}
    )
```

### Enum Handling After Schema Migration

**❌ BAD: Accessing .value on string fields**

```python
# DON'T: Assuming enum objects when you get strings
timezone_value = request.timezone.value  # AttributeError if timezone is string
```

**✅ GOOD: Handle both enum and string**

```python
# DO: Handle string directly (works for both)
timezone_value = request.timezone  # Works for both string and enum
```

### Mock Detection Failures in Tests

**❌ BAD: Tests accidentally using real API clients**

```python
# DON'T: Unreliable mock detection
def _should_use_mock_client(client_id: str | None = None) -> bool:
    # This fails when client_id is empty string but not None
    if client_id is None:
        return True
    return False
```

**✅ GOOD: Explicit mock mode for tests**

```python
# DO: Force mock mode for any falsy credentials
def _should_use_mock_client(client_id: str | None = None) -> bool:
    # Force mock mode for None/empty credentials (test scenario)
    if client_id is None or client_id == "":
        return True
    return is_test_environment()
```

### Field Name Mismatches

**❌ BAD: Manual property name conversion**

```python
# DON'T: Manual conversion when using generated types
await ApiClient.put('/pixel', {
    pixel_id: config.pixelId,  # Bug! Auto-conversion handles this
    required_fields: config.requiredFields  # Wrong!
});
```

**✅ GOOD: Use generated types as-is**

```typescript
import type { PixelConfigRequest } from '@stello/shared-types';

// DO: Use generated types directly
const request: PixelConfigRequest = {
  pixelId: config.pixelId, // camelCase as expected
  requiredFields: config.requiredFields,
};
await ApiClient.put('/pixel', request);
```

### Schema Validation in Tests

**❌ BAD: Validating mock objects with schemas**

```python
# DON'T: This fails if mock structure doesn't match exactly
response = TrainingFileResponse.model_validate(mock_file)
```

**✅ GOOD: Create response objects directly**

```python
# DO: Create schema objects with explicit field mapping
response = TrainingFileResponse(
    id=file.id,
    organization_id=file.organization_id,
    filename=file.filename,
    # All fields explicitly provided
)
```

## External API Integration Anti-Patterns

### Bypassing Transformation Schemas

**❌ BAD: Manually building external API payloads in service layer**

```python
# DON'T: Service manually building Cal.com payload
class EventTypeService:
    async def create_event_type(self, request_data):
        # Manual dict building bypasses transformation layer
        cal_com_data = {
            "title": request_data["title"],
            "customName": request_data.get("custom_name"),  # Manual field mapping
            "length": request_data["duration_minutes"],     # Manual field mapping
            "minimumBookingNotice": request_data["minimum_booking_notice"],
        }

        # No validation, no type safety, scattered transformation logic
        response = await self.cal_com_client.create_event_type(cal_com_data)
```

**✅ GOOD: Using transformation schemas**

```python
# DO: Use schema transformation methods
class EventTypeService:
    async def create_event_type(self, request_data):
        request = CreateEventTypeRequest(**request_data)

        # Clean transformation using schema
        payload = CalComEventTypePayload.from_domain(request)
        cal_com_data = payload.to_api_dict()

        # Type-safe, validated, single source of truth
        response = await self.cal_com_client.create_event_type(cal_com_data)
```

**Why the first approach is problematic:**

- ❌ **No type safety** - easy to make field mapping errors
- ❌ **Scattered transformation logic** - changes require updating multiple places
- ❌ **No validation** - bad data can reach external APIs
- ❌ **Hard to test** - transformation logic mixed with business logic
- ❌ **Maintenance nightmare** - when external API changes, update everywhere

### Mixing External API Format in Internal Schemas

**❌ BAD: Using external field names in internal schemas**

```python
# DON'T: Internal schema using external API field names
class CreateEventTypeRequest(BaseSchema):
    title: str
    length: int  # Wrong! This is Cal.com's field name, not ours
    customName: str | None  # Wrong! CamelCase is their format
```

**✅ GOOD: Keeping domain language in internal schemas**

```python
# DO: Internal schema uses our domain language
class CreateEventTypeRequest(BaseSchema):
    title: str
    duration_minutes: int  # Correct! Our domain field name
    custom_name: str | None  # Correct! Our snake_case convention
```

**Why this matters:**

- ✅ **Domain consistency** - Your API speaks your language, not external vendor's
- ✅ **Change resilience** - If you switch from Cal.com to another provider, internal code unchanged
- ✅ **Clear boundaries** - Obvious distinction between your domain and external systems

### Multiple Transformation Layers Competing

**❌ BAD: Router transforms, then service transforms again**

```python
# DON'T: Dual transformation pipeline
@router.post("/event-types")
async def create_event_type(request: CreateEventTypeRequest):
    # Router transforms using incomplete schema
    payload = IncompletePayload.from_request(request)  # Missing fields!
    event_type_data = payload.to_api_dict()

    # Service ignores router's work and rebuilds manually
    service = EventTypeService()
    await service.create_event_type(event_type_data)  # Rebuilds payload internally

class EventTypeService:
    async def create_event_type(self, event_type_data):
        # Ignores router's transformation, builds own payload
        request = CreateEventTypeRequest(**event_type_data)  # Back to original format

        # Manual payload building because schema was incomplete
        cal_com_data = {
            "title": request.title,
            "customName": request.custom_name,  # Missing from schema!
        }
```

**✅ GOOD: Single transformation point**

```python
# DO: One complete transformation
@router.post("/event-types")
async def create_event_type(request: CreateEventTypeRequest):
    # Router just validates, service handles complete transformation
    service = EventTypeService()
    return await service.create_event_type(request)

class EventTypeService:
    async def create_event_type(self, request: CreateEventTypeRequest):
        # Single, complete transformation using schema
        payload = CalComEventTypePayload.from_domain(request)  # Complete schema
        cal_com_data = payload.to_api_dict()

        response = await self.cal_com_client.create_event_type(cal_com_data)
        return self._process_response(response)
```

### Incomplete External API Schemas

**❌ BAD: External schemas missing fields that services need**

```python
# DON'T: Incomplete transformation schema
class CalComEventTypePayload(CalComBaseSchema):
    title: str
    length: int
    # Missing: customName, destinationCalendar, etc.

    @classmethod
    def from_request(cls, request):
        return cls(
            title=request.title,
            length=request.duration_minutes,
            # Missing transformations for other fields!
        )

# Service forced to bypass schema due to missing fields
class EventTypeService:
    async def create_event_type(self, request):
        # Can't use schema because it's incomplete
        cal_com_data = {
            "title": request.title,
            "length": request.duration_minutes,
            "customName": request.custom_name,  # Manual addition
        }
```

### Split Transformation Responsibility Anti-Pattern

**❌ BAD: Service and integration both doing transformations**

```python
# DON'T: Service handles some transformations, integration handles others
# Service layer doing partial transformation
async def create_event_type(self, request: CreateEventTypeRequest):
    # Service doing field mapping - WRONG LAYER!
    basic_data = {
        "title": request.title,
        "length": request.duration_minutes,  # Transformation in service
    }
    # Integration forced to handle complex objects separately
    return await self.cal_com.create_event_type(basic_data, request.destination_calendar_id)

# Integration doing remaining transformations
class CalComClient:
    async def create_event_type(self, basic_data: dict, calendar_id: str):
        # Integration building complex objects - mixed responsibility!
        payload = {
            "destinationCalendar": {"externalId": calendar_id},  # Complex object here
            **basic_data  # Simple fields from service
        }
```

**✅ GOOD: All transformations in integration schema**

```python
# DO: Complete transformation in one place
class CalComEventTypePayload(CalComBaseSchema):
    @classmethod
    def from_request(cls, request: CreateEventTypeRequest):
        """ALL transformations happen here - single responsibility"""
        return cls(
            length=request.duration_minutes,  # Field mapping
            destinationCalendar=cls._build_destination(request),  # Complex objects
            customName=request.custom_name or "Default template"  # Defaults
        )

# Service: Pure orchestration
async def create_event_type(self, request: CreateEventTypeRequest):
    payload = CalComEventTypePayload.from_request(request)
    return await self.cal_com.create_event_type(payload.to_api_dict())
```

**Rule**: If transformation logic exists in both service and integration layers, consolidate to integration schema.

**✅ GOOD: Complete external API schemas**

```python
# DO: Complete transformation schema
class CalComEventTypePayload(CalComBaseSchema):
    title: str
    length: int
    customName: str | None
    destinationCalendar: CalComDestinationCalendar | None
    minimumBookingNotice: int
    # All fields needed by the API

    @classmethod
    def from_domain(cls, request: CreateEventTypeRequest):
        # Handle all transformations and defaults
        custom_name = request.custom_name
        if not custom_name:
            custom_name = "{Event type title} between {Organizer} and {Scheduler}"

        return cls(
            title=request.title,
            length=request.duration_minutes,
            customName=custom_name,
            minimumBookingNotice=request.minimum_booking_notice,
            # Complete transformation
        )
```

## Testing Anti-Patterns

### Over-Mocking

**❌ BAD: Mocking everything**

```python
# DON'T: Mock every single dependency
@patch('app.features.voice_agents.service.RetellClient')
@patch('app.features.voice_agents.service.DatabaseSession')
@patch('app.features.voice_agents.service.Logger')
@patch('app.features.voice_agents.service.datetime')
@patch('app.features.voice_agents.service.uuid')
def test_create_agent(mock_uuid, mock_datetime, mock_logger, mock_db, mock_retell):
    # Too much mocking makes test brittle and unreadable
    pass
```

**✅ GOOD: Mock at architectural boundaries**

```python
# DO: Mock only external dependencies
@patch('app.features.voice_agents.service.RetellClient')
def test_create_agent(mock_retell):
    mock_retell.return_value.create_agent.return_value = {"agent_id": "test-123"}

    service = VoiceAgentService()
    result = await service.create_agent(test_config, test_db)

    assert result.agent_id == "test-123"
```

### Testing Implementation Details

**❌ BAD: Testing private methods**

```python
# DON'T: Test implementation details
def test_private_method():
    service = VoiceAgentService()
    # Testing private method - breaks with refactoring
    result = service._validate_agent_config(test_config)
    assert result is True
```

**✅ GOOD: Test public behavior**

```python
# DO: Test public API behavior
def test_create_agent_with_invalid_config():
    service = VoiceAgentService()
    # Test behavior through public API
    with pytest.raises(ValidationError):
        await service.create_agent(invalid_config, test_db)
```

### Complex Test Setup

**❌ BAD: Complex test fixtures**

```python
# DON'T: Overly complex test setup
@pytest.fixture
def complex_service():
    mock_retell = Mock()
    mock_calcom = Mock()
    mock_db = Mock()
    mock_logger = Mock()

    # Complex setup with many dependencies
    service = VoiceAgentService()
    service.retell_client = mock_retell
    service.calendar_client = mock_calcom
    service.db = mock_db
    service.logger = mock_logger

    # Complex configuration
    mock_retell.create_agent.return_value = {"agent_id": "test"}
    mock_calcom.create_booking.return_value = {"id": "booking"}

    return service, mock_retell, mock_calcom, mock_db, mock_logger
```

**✅ GOOD: Simple test setup**

```python
# DO: Simple, focused setup
@pytest.fixture
def mock_retell():
    with patch('app.features.voice_agents.service.RetellClient') as mock:
        mock.return_value.create_agent.return_value = {"agent_id": "test-123"}
        yield mock

def test_create_agent(mock_retell):
    service = VoiceAgentService()
    result = await service.create_agent(test_config, test_db)
    assert result.agent_id == "test-123"
```

## Service Evolution Anti-Patterns

### Restructuring Too Early

**❌ BAD: Splitting when orchestrator is still simple**

```python
# DON'T: Split when orchestrator is pure delegation
class VoiceAgentService:  # 120 LOC, 12 methods - still just delegation
    def __init__(self):
        self.creation = CreationService()
        self.config = ConfigurationService()
        # ... 10 more services

    # All methods are 1-2 lines of pure delegation
    async def create_agent(self, config):
        return await self.creation.create_agent(config)

    async def update_config(self, agent_id, settings):
        return await self.config.update_config(agent_id, settings)

    # ... 10 more simple delegation methods

# DON'T: Restructure this - it's still manageable
```

**✅ GOOD: Only restructure when orchestrator gets complex**

```python
# DO: Restructure when methods become complex workflows
class VoiceAgentService:  # 300+ LOC with complex workflows
    async def create_production_ready_agent(self, config):
        """Complex workflow - NOW it's time to restructure"""
        async with db.transaction():
            # 20+ lines of complex business logic
            agent = await self.creation.create_agent(config.base)
            await self.config.apply_production_settings(agent.id, config.prod_settings)
            monitoring_config = self._build_monitoring_config(agent.id, config.monitoring)
            # ... more complex coordination
```

### Splitting by Technical Layers

**❌ BAD: Split by technical concerns**

```python
# DON'T: Split by technical layers
voice_agents/
├── crud/                    # Technical layer - wrong split
│   ├── create_service.py
│   ├── read_service.py
│   └── update_service.py
├── validation/              # Technical layer - wrong split
│   └── validation_service.py
├── persistence/             # Technical layer - wrong split
│   └── persistence_service.py
└── api/                     # Technical layer - wrong split
    └── api_service.py
```

**✅ GOOD: Split by business domains**

```python
# DO: Split by business capabilities
voice_agents/
├── core/                    # Business domain - agent lifecycle
│   ├── creation_service.py
│   ├── deletion_service.py
│   └── retrieval_service.py
├── configuration/           # Business domain - agent settings
│   └── configuration_service.py
└── monitoring/              # Business domain - agent health
    └── monitoring_service.py
```

## Red Flags Checklist

### 🚨 Immediate Action Required

- **Services exceeding 500 LOC or 8 operations** - Split by business domain
- **All models in global directory with >10 model files** - Move feature-specific models to features
- **Integrations importing from features/** - Creates circular dependencies
- **Business logic in integration layers** - Move to service layer
- **Using ports/adapters pattern with single vendors** - Use thin wrappers instead
- **Service-to-service method calls** - Use orchestrator pattern
- **Heavy business logic in orchestration methods** - Create specialized services
- **Integration methods >20 lines** - Probably doing business logic

### ⚠️ Warning Signs

- **Multiple "Manager" or "Orchestrator" classes** - Probably unnecessary layers
- **Services that only call other services** - Consider frontend orchestration
- **Routers with business logic** - Move to service layer
- **API calls just to check existence without using return value** - Let the operation handle validation
- **Complex test setup with many mocks** - Simplify dependencies
- **Testing private methods** - Test public behavior instead
- **Deep inheritance hierarchies** - Favor composition over inheritance

### 🟡 Consider Refactoring

- **Orchestrator methods averaging 5+ lines** - May need restructuring
- **3+ levels of service nesting** - Flatten architecture
- **Services frequently coordinating** - May need different boundaries
- **New team members struggling with architecture** - Simplify structure

## Questions to Ask When You See These Patterns

1. **"Does this service only call other services?"** → Consider frontend orchestration
2. **"What unique business value does this layer provide?"** → If none, eliminate it
3. **"Could the client handle this coordination?"** → Often yes for user-facing workflows
4. **"Are we creating this just to 'have good architecture'?"** → Avoid cargo cult patterns
5. **"Would deleting this make the code simpler?"** → If yes, delete it
6. **"Can new developers understand this in 5 minutes?"** → If no, simplify

## Recovery Strategies

### When You've Over-Engineered

1. **Identify the simplest path** - What's the minimum code to solve the problem?
2. **Remove layers that don't add value** - Delete unnecessary abstractions
3. **Consolidate similar responsibilities** - Combine related operations
4. **Move coordination to the right layer** - Frontend for user workflows, backend for transactions

### When Services Are Too Large

1. **Find natural business boundaries** - Look for domains that rarely interact
2. **Extract specialized services** - Move related operations together
3. **Create thin orchestrator** - Coordinate the new specialized services
4. **Update tests gradually** - Test at new boundaries

### When Architecture Is Confusing

1. **Draw the dependency graph** - Visualize what calls what
2. **Identify circular dependencies** - Break them with orchestrators
3. **Simplify layer boundaries** - Reduce number of layers
4. **Document the happy path** - Show how common operations work

Remember: **Simple, working code is better than complex, "correct" architecture.**

## Related Guides

- [Service Architecture](service-architecture.md) - The correct patterns to use instead
- [Decision Frameworks](decision-frameworks.md) - How to make better choices
- [Integration Patterns](integration-patterns.md) - Proper integration layer design
