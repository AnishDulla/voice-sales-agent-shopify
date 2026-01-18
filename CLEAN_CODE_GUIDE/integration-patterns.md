# Integration Patterns & External API Handling

This guide covers how to integrate with external services using thin wrappers, compensation patterns, and proper error handling.

## Integration Layer Rules (Thin Wrappers, Not Ports)

**Key Principle:** Features can import integrations directly. Keep integrations thin and focused on SDK wrapping. **Avoid the ports/adapters pattern for small applications** - it's over-engineering at Stello AI's current scale.

**✅ Features Import Integrations Directly:**

```python
# app/features/voice_agents/service.py
from app.integrations.retell.client import RetellClient
from app.integrations.calcom.client import CalComClient

class VoiceAgentService:
    def __init__(self):
        self.retell = RetellClient()
        self.calendar = CalComClient()

    async def create_agent_with_booking(self, config: dict, db: AsyncSession):
        # Business orchestration
        booking = await self.calendar.create_booking(config['booking_data'])
        agent_config = self._build_agent_config(booking)
        result = await self.retell.create_agent(agent_config)

        # Save to database
        agent = VoiceAgent(**result, booking_id=booking['id'])
        db.add(agent)
        await db.commit()
        return agent
```

**✅ Integration Layer: Thin SDK Wrappers Only**

```python
# app/integrations/retell/client.py
from retell import AsyncRetell
import logging

class RetellClient:
    """Thin wrapper - error handling + logging only"""
    def __init__(self):
        self.client = AsyncRetell(api_key=settings.retell_api_key)

    async def create_agent(self, config: dict) -> dict:
        try:
            result = await self.client.agent.create(**config)
            logging.info(f"Created Retell agent: {result.agent_id}")
            return {"agent_id": result.agent_id, "name": result.name}
        except RetellError as e:
            logging.error(f"Retell API error: {e}")
            raise ExternalServiceError(f"Failed to create agent: {e}")
```

**One-Way Dependency Flow:**

- ✅ Features → Integrations → External SDKs
- ❌ Integrations never import from features/ (creates cycles)

**What Integrations Should Do:**

- Wrap SDKs with consistent error handling
- Handle retries, timeouts, logging
- Normalize response formats
- Manage API keys/configuration

**What Integrations Should NOT Do:**

- Import from features/ (creates circular dependencies)
- Contain business logic or validation
- Handle database operations
- Orchestrate workflows

## The Database Commit Litmus Test: `/app/integrations/` vs `/app/features/`

**Key Decision Framework**: Where does the database commit happen?

This litmus test provides a clear, objective boundary between infrastructure (integrations) and business logic (features):

- **Database commit in code → `/app/features/`** (business logic layer)
- **Only HTTP/API calls, returns data → `/app/integrations/`** (infrastructure layer)

**Additional Principle**: `/app/integrations/` should be SDK abstractions

Think of each integration as building an SDK for that external service:
- Pure API communication
- No business logic
- No model imports from features
- No database operations

### Real Examples from Stello Codebase

**✅ Google OAuth: Correct Layering**

```python
# app/integrations/google_oauth/flow_wrapper.py (INFRASTRUCTURE)
class GoogleOAuthFlowWrapper:
    """Thin wrapper - pure OAuth flow, no database operations"""

    def fetch_token(self, flow: Any, code: str) -> dict[str, Any]:
        """Returns tokens - DOES NOT commit to database"""
        token = flow.fetch_token(code=code)
        logger.info("Token exchange successful")
        return token  # ← Returns data, no database commit

# app/features/calendar/connected_calendars/google_connection_service.py (BUSINESS LOGIC)
class GoogleConnectionService:
    """Domain service - handles OAuth + database persistence"""

    async def complete_oauth_callback(self, code: str, state: str):
        """Business logic: OAuth + database commit"""
        # Phase 1: Get tokens from infrastructure (no DB)
        flow_wrapper = get_google_oauth_flow_wrapper()
        tokens = flow_wrapper.fetch_token(flow, code)  # ← Infrastructure call

        # Phase 2: Business logic + database commit
        async with self.db_session.begin():  # ← Database transaction
            calendar = ConnectedCalendar(
                organization_id=org_id,
                oauth_tokens=tokens,
                # ... business logic fields
            )
            self.db_session.add(calendar)
            await self.db_session.commit()  # ← COMMIT happens in features layer!

        return {"success": True}
```

**✅ Calendly: Correct Layering**

```python
# app/integrations/calendly/client.py (INFRASTRUCTURE)
class CalendlyClient:
    """SDK wrapper - pure API operations"""

    async def get_scheduled_events(self, user_uri: str) -> dict:
        """Returns API data - no database operations"""
        response = await self.client.get(
            "/scheduled_events",
            params={"user": user_uri}
        )
        return response.json()  # ← Returns data, no database commit

# app/features/integrations/oauth/calendly_oauth.py (BUSINESS LOGIC)
class CalendlyOAuthService:
    """Domain service - orchestrates OAuth + storage"""

    async def complete_oauth(self, code: str, state: str, db: AsyncSession):
        """Business logic: OAuth + database commit"""
        # Phase 1: Gather external data (integration layer)
        client = get_calendly_client()
        tokens = await client.exchange_code_for_token(code)  # ← Infrastructure
        user_info = await client.get_current_user(tokens["access_token"])  # ← Infrastructure

        # Phase 2: Business logic + database commit
        integration = await self.integration_service.upsert_integration(
            db=db,  # ← Database session
            organization_id=org_id,
            provider="calendly",
            oauth_data=tokens,  # ← Business logic decides what to store
        )
        await db.commit()  # ← COMMIT happens in features layer!

        return {"success": True, "integration_id": integration.id}
```

**✅ GoHighLevel: Correct Layering**

```python
# app/integrations/gohighlevel/client.py (INFRASTRUCTURE)
class GoHighLevelClient:
    """SDK wrapper - pure API operations"""

    async def create_contact_note(self, access_token: str, contact_id: str, note: str):
        """Makes API call - no database operations"""
        response = await self.http_client.post(
            f"/contacts/{contact_id}/notes",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"body": note}
        )
        return response.json()  # ← Returns data, no database commit

# app/features/integrations/oauth/gohighlevel_oauth.py (BUSINESS LOGIC)
class GHLOAuthService:
    """Domain service - OAuth flow + database persistence"""

    async def complete_oauth(self, code: str, state: str, db: AsyncSession):
        """Business logic: OAuth + database commit"""
        # Phase 1: Gather external data (infrastructure)
        client = get_ghl_client()
        tokens = await client.exchange_code_for_token(code)  # ← Infrastructure

        # Phase 2: Business logic + database commit
        integration = await self.integration_service.upsert_integration(
            db=db,  # ← Database session
            organization_id=org_id,
            provider="gohighlevel",
            provider_category="crm",
            oauth_data=tokens,
            capabilities=["webhook_events", "sync_contacts"],  # ← Business logic
        )
        await db.commit()  # ← COMMIT happens in features layer!

        return {"success": True}
```

### Anti-Pattern: Database Operations in Integrations Layer

**❌ DON'T: Integration layer committing to database**

```python
# app/integrations/retell/client.py (WRONG LAYER!)
class RetellClient:
    def __init__(self, db_session: AsyncSession):  # ← RED FLAG: DB session in integration
        self.db = db_session

    async def create_agent(self, config: dict):
        """VIOLATES LAYERING: Integration doing business logic + database commit"""
        # External API call (CORRECT for integrations)
        result = await self.client.agent.create(**config)

        # Database commit (WRONG LAYER - belongs in features!)
        agent = VoiceAgent(  # ← Importing models from features
            agent_id=result.agent_id,
            organization_id=config["org_id"],  # ← Business logic decisions
        )
        self.db.add(agent)
        await self.db.commit()  # ← VIOLATES: Database commit in infrastructure!

        return agent
```

**✅ DO: Separate infrastructure and business logic**

```python
# app/integrations/retell/client.py (INFRASTRUCTURE)
class RetellClient:
    """SDK wrapper - pure API operations, no database"""

    async def create_agent(self, config: dict) -> dict:
        """Returns API response - no database operations"""
        result = await self.client.agent.create(**config)
        return {"agent_id": result.agent_id, "name": result.name}  # ← Just data

# app/features/retell/voice_agents/creation_service.py (BUSINESS LOGIC)
class AgentCreationService:
    """Domain service - orchestrates API + database"""

    async def create_agent(self, request: AgentRequest, db: AsyncSession):
        """Business logic: API call + database commit"""
        # Phase 1: Infrastructure call
        retell_client = RetellClient()
        api_result = await retell_client.create_agent(request.to_api_dict())

        # Phase 2: Business logic + database commit
        async with db.begin():
            agent = VoiceAgent(
                agent_id=api_result["agent_id"],
                organization_id=request.organization_id,  # ← Business logic
                is_active=True,  # ← Business logic
            )
            db.add(agent)
            await db.commit()  # ← COMMIT in features layer!

        return agent
```

### Decision Checklist: `/app/integrations/` vs `/app/features/`

Ask yourself these questions when deciding where code belongs:

**Put in `/app/integrations/` when:**
- ✅ Code only makes HTTP/API calls to external services
- ✅ Returns raw or lightly transformed API data
- ✅ No database session parameter needed
- ✅ No model imports from `/app/features/` or `/app/models/`
- ✅ Could be published as a standalone SDK package
- ✅ No business logic decisions (org ownership, feature flags, etc.)

**Put in `/app/features/` when:**
- ✅ Code commits to database (creates/updates/deletes records)
- ✅ Requires database session parameter
- ✅ Imports models from `/app/models/` or feature models
- ✅ Makes business logic decisions (permissions, validation rules)
- ✅ Orchestrates multiple integrations or services
- ✅ Handles domain-specific error cases beyond API errors

### Benefits of This Boundary

1. **Testability**: Integrations can be tested without database
2. **Reusability**: Integration clients could be extracted as standalone libraries
3. **Clarity**: Clear separation between "talking to external APIs" and "business logic"
4. **Maintainability**: Integration changes don't affect business logic and vice versa
5. **Import Safety**: Prevents circular dependencies (integrations never import features)

### Shared Infrastructure in Integrations Layer

**Pattern:** Some integration concerns are shared across multiple platforms and belong in the integrations layer as reusable infrastructure.

**✅ Valid Shared Infrastructure Examples:**

```python
# app/integrations/oauth/token_manager.py
class TokenManager:
    """Generic OAuth token refresh logic shared by all OAuth integrations"""
    async def get_valid_token(self, integration: Integration, oauth_client: BaseOAuthClient) -> str:
        if self._is_token_expired(integration):
            new_tokens = await oauth_client.refresh_access_token(...)
            integration.oauth_data["access_token"] = new_tokens["access_token"]
        return integration.oauth_data.get("access_token")

# app/integrations/oauth/base.py
class BaseOAuthClient(Protocol):
    """Protocol for OAuth-based integrations"""
    async def get_authorization_url(self, state: str) -> str: ...
    async def exchange_code_for_token(self, code: str) -> dict: ...
    async def refresh_access_token(self, refresh_token: str) -> dict: ...
```

**Platform-Specific Implementation:**

```python
# app/integrations/gohighlevel/oauth.py
from app.integrations.oauth import BaseOAuthClient, TokenManager

class GoHighLevelOAuthClient:
    """GHL-specific OAuth implementation using shared infrastructure"""
    def __init__(self):
        self.token_manager = TokenManager()

    async def get_authorization_url(self, state: str) -> str:
        return f"https://marketplace.gohighlevel.com/oauth/chooselocation?..."

    async def exchange_code_for_token(self, code: str) -> dict:
        # GHL-specific token exchange logic
        pass
```

**When to Create Shared Infrastructure:**

✅ **DO create shared infrastructure when:**
- 3+ integrations need the same utility (OAuth, webhooks, rate limiting)
- Logic is purely technical, not business-specific
- Reduces code duplication across integrations
- No dependencies on features/ layer

❌ **DON'T create shared infrastructure when:**
- Only 1-2 integrations need it (keep it local until proven reusable)
- Logic contains business rules or domain concepts
- Would require importing from features/ layer

**Technical Debt Note:**

Current OAuth implementations (Calendly, Google Calendar, Slack) predate the shared `integrations/oauth/` pattern. Future refactoring should migrate these to use the shared infrastructure:

- `features/calendly/oauth_service.py` → should use `integrations/oauth/TokenManager`
- `integrations/google_oauth/client.py` → should implement `BaseOAuthClient` protocol
- `integrations/slack/oauth_client.py` → should use shared OAuth utilities

This migration is deferred to Phase 2 post-refactor work to avoid scope creep.

## OAuth as a Domain: The Connection Lifecycle Pattern

**Key Insight:** Some integration layer concerns are actually legitimate domains, not just shared utilities. "Connections" (OAuth flows + token storage + health monitoring) is a valid bounded context worthy of being its own vertical slice.

**The Pattern We Use:**

```
features/integrations/
├── oauth/                          # ✅ Legitimate domain (not just utility)
│   ├── __init__.py
│   └── gohighlevel_oauth.py        # Platform-specific OAuth orchestration
├── crud.py                         # Shared IntegrationService (token storage)
├── router.py                       # OAuth callback endpoints
└── models.py                       # Integration model (connection state)
```

**Decision Criteria: Is This a Domain or a Utility?**

✅ **It's a legitimate domain when:**
- **Owns complete lifecycle**: OAuth flow → token storage → health monitoring → re-authorization
- **Has persistent state**: `Integration` model with `oauth_data`, `connection_status`, `webhook_config`
- **Has user-facing workflows**: Authorization redirects, connection health UI, disconnection flows
- **Multiple features depend on it but don't own it**: Calendly needs tokens, Slack needs tokens, GoHighLevel needs tokens - but none of them should own the OAuth infrastructure

❌ **It's just a utility when:**
- Purely technical helper (date formatting, string parsing)
- Stateless operations with no database models
- No user-facing flows or UI
- Single feature uses it exclusively

**The Pragmatic Compromise (Best of Both Worlds):**

Instead of forcing every feature to duplicate OAuth logic for "pure" vertical slices, we centralize OAuth infrastructure while keeping domain behavior distributed:

1. **Centralize OAuth infrastructure** in `features/integrations/oauth/`
   - OAuth flow orchestration (authorization URL, code exchange, token refresh)
   - Connection state management (connected, disconnected, expired)
   - Token retrieval and validation

2. **Share IntegrationService (crud.py)** for token storage/retrieval
   - All OAuth flows write to single `Integration` model
   - Features read tokens through consistent interface
   - No duplication of token refresh logic

3. **Each feature owns its domain behavior:**
   - **Calendly** → appointment sync + webhook handling
   - **Slack** → message triggers + workflow actions
   - **GoHighLevel** → contact field mapping + call sync

**Real Example: GoHighLevel OAuth Flow**

```python
# features/integrations/oauth/gohighlevel_oauth.py
class GHLOAuthService:
    """Orchestrates OAuth flow and delegates storage to IntegrationService"""
    def __init__(self):
        self.client = get_ghl_client()
        self.integration_service = IntegrationService()  # From crud.py

    async def complete_oauth(self, code: str, state: str, db: AsyncSession):
        # Phase 1: Gather external data (OAuth-specific logic)
        external_data = await self._gather_external_data(code, state)

        # Phase 2: Delegate storage to IntegrationService (shared CRUD)
        integration = await self.integration_service.upsert_integration(
            db=db,
            organization_id=external_data["org_id"],
            provider="gohighlevel",
            provider_category="crm",
            oauth_data=external_data["oauth_data"],
            capabilities=["webhook_events", "sync_contacts", "sync_calls"],
        )

        return {"success": True, "integration_id": integration.id}
```

```python
# features/integrations/router.py
@router.post("/crm/sync/connect")
async def connect_gohighlevel(request: GHLConnectRequest, org_context: OrganizationContextDep, db: DatabaseDep):
    """OAuth endpoint owned by integrations domain"""
    service = GHLOAuthService()
    result = await service.connect(org_id=org_context.organization_id, redirect_uri=request.redirect_uri, db=db)
    return GHLConnectResponse(auth_url=result["auth_url"], state=result["state"])
```

```python
# features/external_sync/gohighlevel/sync_service.py
class GHLSyncService:
    """Domain service that uses tokens from integrations domain"""
    async def sync_call_to_ghl(self, call_log: RetellCallLog, contact: Contact):
        # Get integration from integrations domain
        integration = await self._get_ghl_integration(call_log.organization_id)

        # Use token to sync call (domain-specific logic)
        access_token = integration.oauth_data["access_token"]
        await self.ghl_client.create_contact_note(access_token, contact_id, note_body)
```

**Why This Follows DDD Principles:**

- **Bounded Context**: "Connections" is a distinct domain with clear boundaries
- **Ubiquitous Language**: "integration", "connection", "oauth_data", "token refresh"
- **Ownership**: Integrations domain owns OAuth flows; features delegate connection management
- **Vertical Slice**: Integrations owns its complete stack (OAuth → router → storage → health)

**Anti-Pattern to Avoid:**

❌ **Don't duplicate OAuth flows in each feature just to maintain "pure" vertical slices:**

```python
# DON'T: Each feature duplicating OAuth logic
features/calendly/oauth_service.py      # 200 lines of OAuth logic
features/slack/oauth_service.py         # 200 lines of OAuth logic (duplicate)
features/gohighlevel/oauth_service.py   # 200 lines of OAuth logic (duplicate)
```

✅ **DO recognize when centralization is the right architectural choice:**

```python
# DO: Centralized OAuth infrastructure
features/integrations/oauth/
├── calendly_oauth.py        # Platform-specific OAuth config
├── slack_oauth.py           # Platform-specific OAuth config
└── gohighlevel_oauth.py     # Platform-specific OAuth config

# Each imports shared IntegrationService for token storage
```

**Philosophical Note: Vertical Slice ≠ Isolated Forever**

Vertical slice architecture means each domain owns its full stack. If "connections" is a valid domain (and it is), then it should own OAuth infrastructure. You're not breaking the architecture by centralizing OAuth - you're **evolving it into a domain-driven vertical where "Integrations" is its own bounded context**.

**Technical Debt Note:**

Current OAuth implementations (Calendly, Google Calendar, Slack) predate this pattern and have OAuth logic scattered in their feature directories:

- `features/calendly/oauth_service.py` → should migrate to `integrations/oauth/calendly_oauth.py`
- `integrations/google_oauth/client.py` → should implement shared OAuth patterns
- `features/workflows/actions/slack/oauth_service.py` → should migrate to `integrations/oauth/slack_oauth.py`

Migration priority: **Low** (existing implementations work, consolidate during next refactor of those features)

## Complete Transformation Layer Pattern

**Complete Transformation Rule**: All field mappings, object building, and defaults must be in the integration schema layer, not split between service and integration.

**✅ Complete Transformation in Integration Schema:**

```python
# app/integrations/cal_com/schemas.py
class CalComEventTypePayload(CalComBaseSchema):
    @classmethod
    def from_request(cls, request: CreateEventTypeRequest, **kwargs):
        """Handles ALL transformations - no service layer involvement"""
        return cls(
            length=request.duration_minutes,  # Field mapping
            destinations=cls._build_destination(request),  # Complex object
            locations=cls._build_locations(request),  # Array transformation
            customName=request.custom_name or "{Event type title} between {Organizer} and {Scheduler}"  # Defaults
        )
```

**✅ Service Layer: Pure Orchestration:**

```python
# app/features/calendar/service.py
async def create_event_type(self, request: CreateEventTypeRequest):
    payload = CalComEventTypePayload.from_request(request, calendar_type="google")
    return await self.cal_com.create_event_type(payload.to_api_dict())
```

**Decision Point**: If service layer is doing ANY field transformation (mapping, defaults, object building), move it to integration schema.

**Factory Method Pattern**: When external APIs need complex objects, use `from_domain()` or `from_request()` class methods on integration schemas.

## When to Use Thin Wrappers vs Ports Pattern

**✅ Use Thin Wrappers When (Stello AI's Current State):**

- Single vendor per integration type (e.g., only Retell for voice)
- Team size < 10 developers
- < 5 external integrations total
- Simple CRUD operations with external APIs
- Vendor switching is unlikely in next 12 months

**⚠️ Consider Ports Pattern When:**

- Multiple vendors for same capability (Retell + Twilio for voice)
- Team size > 15 developers
- > 10 external integrations
- Complex vendor-specific business logic
- High likelihood of vendor switching
- Regulatory requirements for vendor independence

**❌ Over-Engineered: Ports Pattern for Small Apps**

```python
# DON'T: Unnecessary abstraction for single vendor
from abc import ABC, abstractmethod

class VoiceAgentPort(ABC):
    @abstractmethod
    async def create_agent(self, config: dict) -> dict: ...

class RetellAdapter(VoiceAgentPort):  # Only one implementation
    async def create_agent(self, config: dict) -> dict:
        return await self.client.create_agent(config)

# Feature service now depends on abstraction it owns
class VoiceAgentService:
    def __init__(self, voice_port: VoiceAgentPort):  # Unnecessary complexity
        self.voice_client = voice_port
```

**✅ Right-Sized: Thin Wrapper for Single Vendor**

```python
# DO: Simple, direct wrapper when you have one vendor
class RetellClient:
    async def create_agent(self, config: dict) -> dict:
        try:
            result = await self.client.agent.create(**config)
            return {"agent_id": result.agent_id, "name": result.name}
        except RetellError as e:
            raise ExternalServiceError(f"Failed to create agent: {e}")

# Feature service imports wrapper directly
class VoiceAgentService:
    def __init__(self):
        self.retell = RetellClient()  # Simple, testable
```

**Why Thin Wrappers Win for Small Apps:**

- ✅ **Testability**: Easy to mock `RetellClient` in tests
- ✅ **Vendor Independence**: Still abstracted from raw SDK
- ✅ **Simplicity**: No abstract base classes or dependency injection
- ✅ **Maintainability**: Less code, fewer layers to understand
- ✅ **Vendor Switch Cost**: Change one wrapper class vs scattered SDK calls

## External API Error Handling & Cleanup Patterns

### The Compensation Pattern for External APIs

When orchestrating operations that involve external APIs, failures require careful cleanup to maintain system consistency:

```python
class VoiceAgentService:
    async def create_complete_call_system(self, request: CallSystemRequest, org_id: str, db: AsyncSession) -> CallSystemResponse:
        """Atomic operation with external API compensation"""
        created_resources = {}

        try:
            # Step 1: Create conversation flow (external Retell API)
            flow_result = await self.retell_client.create_conversation_flow(request.flow_config)
            created_resources["flow_id"] = flow_result["conversation_flow_id"]

            # Step 2: Create voice agent (external Retell API)
            agent_result = await self.retell_client.create_agent({
                "name": request.agent_name,
                "voice_id": request.voice_id,
                "conversation_flow_id": created_resources["flow_id"]
            })
            created_resources["agent_id"] = agent_result["agent_id"]

            # Step 3: Assign phone number (external Retell API)
            phone_result = await self.retell_client.assign_phone_number({
                "agent_id": created_resources["agent_id"],
                "area_code": request.area_code
            })
            created_resources["phone_number"] = phone_result["phone_number"]

            # Step 4: Save configuration to database (local operation)
            async with db.begin():
                config = RetellConfiguration(
                    organization_id=org_id,
                    agent_id=created_resources["agent_id"],
                    flow_id=created_resources["flow_id"],
                    phone_number=created_resources["phone_number"],
                    is_active=True
                )
                db.add(config)
                await db.commit()

            return CallSystemResponse(
                success=True,
                agent_id=created_resources["agent_id"],
                phone_number=created_resources["phone_number"],
                message="Call system created successfully"
            )

        except Exception as e:
            logger.error(f"Call system creation failed: {e}")
            # Compensation: Clean up any external resources that were created
            await self._cleanup_external_resources(created_resources)

            return CallSystemResponse(
                success=False,
                error="call_system_creation_failed",
                message=f"Failed to create call system: {str(e)}"
            )

    async def _cleanup_external_resources(self, created_resources: dict[str, str]) -> None:
        """Compensation pattern: Clean up external API resources"""
        cleanup_errors = []

        # Clean up in reverse order of creation
        if "phone_number" in created_resources:
            try:
                await self.retell_client.release_phone_number(created_resources["phone_number"])
                logger.info(f"Cleaned up phone number: {created_resources['phone_number']}")
            except Exception as e:
                cleanup_errors.append(f"Failed to release phone number: {e}")

        if "agent_id" in created_resources:
            try:
                await self.retell_client.delete_agent(created_resources["agent_id"])
                logger.info(f"Cleaned up agent: {created_resources['agent_id']}")
            except Exception as e:
                cleanup_errors.append(f"Failed to delete agent: {e}")

        if "flow_id" in created_resources:
            try:
                await self.retell_client.delete_conversation_flow(created_resources["flow_id"])
                logger.info(f"Cleaned up conversation flow: {created_resources['flow_id']}")
            except Exception as e:
                cleanup_errors.append(f"Failed to delete conversation flow: {e}")

        if cleanup_errors:
            # Log cleanup failures but don't raise - original error is more important
            logger.warning(f"Cleanup completed with errors: {cleanup_errors}")
            # Consider alerting for manual cleanup if critical
```

### Idempotency for Retry Scenarios

Make operations safe to retry by designing them to be idempotent:

```python
class VoiceAgentService:
    async def create_agent_idempotent(self, request: AgentCreateRequest, org_id: str, db: AsyncSession) -> AgentCreateResponse:
        """Idempotent agent creation - safe to retry"""

        # Check if agent already exists with same parameters
        existing_config = await db.execute(
            select(RetellConfiguration).where(
                and_(
                    RetellConfiguration.organization_id == org_id,
                    RetellConfiguration.agent_name == request.agent_name,
                    RetellConfiguration.is_active == True
                )
            )
        )
        existing = existing_config.scalar_one_or_none()

        if existing:
            logger.info(f"Agent already exists: {existing.agent_id}")
            return AgentCreateResponse(
                success=True,
                agent_id=existing.agent_id,
                message="Agent already exists",
                created=False
            )

        # Create new agent using compensation pattern
        return await self.create_complete_call_system(request, org_id, db)

    async def update_agent_configuration_idempotent(self, agent_id: str, config: dict, db: AsyncSession) -> UpdateResponse:
        """Idempotent configuration update"""

        # Get current configuration
        current_config = await self.retell_client.get_agent_configuration(agent_id)

        # Compare with requested configuration
        if self._configurations_equal(current_config, config):
            logger.info(f"Agent {agent_id} already has requested configuration")
            return UpdateResponse(success=True, message="No changes needed", updated=False)

        # Apply configuration update
        try:
            await self.retell_client.update_agent_configuration(agent_id, config)
            return UpdateResponse(success=True, message="Configuration updated", updated=True)
        except Exception as e:
            logger.error(f"Failed to update agent configuration: {e}")
            return UpdateResponse(success=False, error=str(e))
```

### Transaction Boundaries with External Services

Use database transactions strategically when mixing local and external operations:

```python
class VoiceAgentService:
    async def migrate_agent_atomically(self, agent_id: str, new_template: str, preserve_customizations: bool, db: AsyncSession) -> MigrationResponse:
        """Atomic migration: All operations succeed or all fail"""

        # Get current state outside transaction
        current_agent = await self.retrieval_service.get_agent_by_id(agent_id, db)
        if not current_agent:
            return MigrationResponse(success=False, error="Agent not found")

        customizations = {}
        if preserve_customizations:
            customizations = await self.config_service.extract_customizations(current_agent)

        # External operations first (no rollback possible)
        external_resources = {}
        try:
            # Create new flow with template
            new_flow = await self.retell_client.create_conversation_flow({
                "template": new_template,
                "customizations": customizations
            })
            external_resources["new_flow_id"] = new_flow["conversation_flow_id"]

            # Update agent to use new flow
            await self.retell_client.update_agent_configuration(agent_id, {
                "conversation_flow_id": external_resources["new_flow_id"]
            })

            # Now update database in transaction
            async with db.begin():
                # Update local configuration
                result = await db.execute(
                    select(RetellConfiguration).where(RetellConfiguration.agent_id == agent_id)
                )
                config = result.scalar_one()

                old_flow_id = config.conversation_flow_id
                config.conversation_flow_id = external_resources["new_flow_id"]
                config.template_version = new_template
                config.migration_timestamp = datetime.utcnow()

                await db.commit()

                # Clean up old flow after successful database update
                try:
                    await self.retell_client.delete_conversation_flow(old_flow_id)
                except Exception as e:
                    logger.warning(f"Failed to clean up old flow {old_flow_id}: {e}")
                    # Don't fail the operation - cleanup can be done later

                return MigrationResponse(
                    success=True,
                    old_flow_id=old_flow_id,
                    new_flow_id=external_resources["new_flow_id"],
                    message="Agent migrated successfully"
                )

        except Exception as e:
            logger.error(f"Migration failed: {e}")

            # Compensation: Clean up external resources
            if "new_flow_id" in external_resources:
                try:
                    await self.retell_client.delete_conversation_flow(external_resources["new_flow_id"])
                except Exception as cleanup_error:
                    logger.error(f"Failed to cleanup new flow during rollback: {cleanup_error}")

            return MigrationResponse(
                success=False,
                error=f"Migration failed: {str(e)}",
                message="Migration rolled back"
            )
```

### Error Handling Decision Framework

**External API Error Categories:**

1. **Transient Errors** (retry-able): Network timeouts, rate limits, temporary service unavailability
2. **Client Errors** (non-retryable): Invalid requests, authentication failures, resource not found
3. **Server Errors** (potentially retryable): Internal server errors, service degradation

**Handling Strategy:**

```python
class ExternalAPIHandler:
    async def handle_external_operation(self, operation_func, *args, max_retries=3, **kwargs):
        """Generic external API operation handler with retry logic"""

        for attempt in range(max_retries + 1):
            try:
                return await operation_func(*args, **kwargs)

            except ClientError as e:
                # Don't retry client errors (4xx)
                logger.error(f"Client error (non-retryable): {e}")
                raise ExternalServiceError(f"Invalid request: {e}")

            except (NetworkError, TimeoutError, ServerError) as e:
                if attempt == max_retries:
                    logger.error(f"External API failed after {max_retries} retries: {e}")
                    raise ExternalServiceError(f"Service unavailable after retries: {e}")

                # Exponential backoff for retryable errors
                wait_time = 2 ** attempt
                logger.warning(f"Retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
                continue

            except Exception as e:
                # Unknown errors - don't retry
                logger.error(f"Unknown external API error: {e}")
                raise ExternalServiceError(f"Unexpected error: {e}")
```

## External API Integration Decision Framework

**Choose Compensation Pattern When:**

✅ **Multiple external APIs in sequence** - Each step creates resources that need cleanup
✅ **Expensive operations** - Creating agents, phone numbers, flows costs money/quota
✅ **User-facing failures** - Users need clear error messages and system stays consistent
✅ **Retryable operations** - Operations might succeed on retry, need cleanup for failed attempts

**Skip Compensation When:**

❌ **Read-only operations** - GET requests don't create resources to clean up
❌ **Idempotent APIs** - External API handles duplicates gracefully
❌ **Fire-and-forget operations** - Background tasks where immediate consistency isn't critical
❌ **Internal-only operations** - No external resources created

### Error Handling Strategy by API Type

| API Characteristic            | Retry Strategy                            | Compensation Strategy      | Example                                  |
| ----------------------------- | ----------------------------------------- | -------------------------- | ---------------------------------------- |
| **Idempotent**                | Aggressive retry with exponential backoff | None (safe to retry)       | GET requests, PUT with unique IDs        |
| **Non-idempotent, Expensive** | Limited retry + compensation              | Full resource cleanup      | Create Retell agent, assign phone number |
| **Non-idempotent, Cheap**     | Limited retry, accept some failures       | Optional cleanup           | Send notification, log events            |
| **Stateful sequence**         | No retry + compensation                   | Reverse operation sequence | Multi-step onboarding flows              |

### Decision Questions for External API Operations

**Before implementing any external API operation, ask:**

1. **Resource Creation**: Does this operation create external resources that cost money/quota?
   - **Yes** → Implement compensation pattern
   - **No** → Simple error handling sufficient

2. **Operation Sequence**: Are multiple external APIs called in sequence?
   - **Yes** → Track created resources, implement reverse cleanup
   - **No** → Single operation error handling

3. **Retry Safety**: Is this operation safe to retry?
   - **Yes** → Implement exponential backoff retry
   - **No** → Implement idempotency checks or accept failure

4. **User Impact**: Do users need to know exactly what failed?
   - **Yes** → Granular error messages, partial success handling
   - **No** → Simple success/failure response

5. **System Consistency**: Must the system stay consistent if this fails?
   - **Yes** → Implement full compensation
   - **No** → Log error and continue

**Golden Rule**: If it creates external resources that cost money or quota, implement compensation.

## Client Factory Pattern (Environment-Based Configuration)

**Problem**: Adding mock mode settings for each integration bloats the Settings class. Each new integration adds properties like `use_{service}_mock_api`, `{service}_mock_mode`, etc.

**Solution**: Factory functions detect environment and configure clients appropriately. Keep Settings as a thin credential layer only.

### Pattern Overview

1. **Factory function** detects test environment (not Settings)
2. **Client constructor** accepts configuration parameters
3. **Client methods** use those parameters internally

### Example: Twilio with Mock API Support

```python
# app/integrations/twilio/client.py
import os

def get_twilio_client() -> TwilioClient | MockTwilioClient:
    """Get Twilio client based on environment."""
    # Test override (for VCR E2E tests)
    if _twilio_client_override is not None:
        return _twilio_client_override

    # Detect environment
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_test = environment == "test" or os.getenv("PYTEST_CURRENT_TEST") is not None

    # Unit tests: Pure mock (no HTTP)
    if is_test:
        from app.integrations.twilio.mocks import MockTwilioClient
        return MockTwilioClient()

    # Real client: Environment determines mock API usage
    use_mock_api = environment in ("development", "staging")
    return TwilioClient(use_mock_api=use_mock_api)


class TwilioClient:
    def __init__(self, use_mock_api: bool = False):
        self._use_mock_api = use_mock_api
        self.client = TwilioSDKClient(
            settings.twilio_account_sid,
            settings.twilio_auth_token
        )

    def create_brand_registration(
        self,
        customer_profile_sid: str,
        a2p_profile_sid: str,
        brand_type: str = "STANDARD",
    ) -> dict[str, Any]:
        # Pass mock=True/False based on constructor config
        brand = self.client.messaging.a2p_compliance.brands.create(
            customer_profile_bundle_sid=customer_profile_sid,
            a_2_p_profile_bundle_sid=a2p_profile_sid,
            brand_type=brand_type,
            mock=self._use_mock_api,  # ← Environment-controlled
        )
        return {"sid": brand.sid, "status": brand.status}
```

### Benefits

- ✅ **No Settings bloat** - No `use_{service}_mock_api` properties needed
- ✅ **Explicit configuration** - Client knows its configuration at construction time
- ✅ **Testable** - Can create client with any configuration for testing
- ✅ **Environment-driven** - Behavior matches existing patterns in codebase

### When to Use This Pattern

Use this pattern when:
- External API has a "mock" or "test" mode parameter
- Test credentials behave differently than production (e.g., Twilio's `mock=True`)
- You want to avoid adding logic properties to Settings class
- Client configuration should be determined at construction, not per-call

### What to Keep in Settings

Settings should only contain **credentials** (thin env var passthrough):

```python
# ✅ DO: Just credentials
@property
def twilio_account_sid(self) -> str | None:
    return os.getenv("TWILIO_ACCOUNT_SID")

@property
def twilio_auth_token(self) -> str | None:
    return os.getenv("TWILIO_AUTH_TOKEN")

# ❌ DON'T: Logic properties
@property
def use_twilio_mock_api(self) -> bool: ...  # ← Bloat!

@property
def twilio_mock_mode(self) -> str: ...  # ← Bloat!
```

### Testing Modes Summary

| Environment | Client | Configuration | Behavior |
|-------------|--------|---------------|----------|
| **test** | `MockTwilioClient` | N/A | Pure mock (no HTTP, instant) |
| **development** | `TwilioClient` | `use_mock_api=True` | Real HTTP, passes `mock=True` to API |
| **staging** | `TwilioClient` | `use_mock_api=True` | Real HTTP, passes `mock=True` to API |
| **production** | `TwilioClient` | `use_mock_api=False` | Real HTTP, real operations |

## Related Guides

- [Service Architecture](service-architecture.md) - How to organize services that use these integration patterns
- [API Design Patterns](api-design-patterns.md) - How these integrations fit into the three-layer API pattern
- [Testing Strategy](testing-strategy.md) - How to test external integrations and compensation patterns
- [Decision Frameworks](decision-frameworks.md) - Decision matrices for integration and error handling choices
