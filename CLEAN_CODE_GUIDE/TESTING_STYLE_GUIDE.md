# Testing Style Guide

Best practices and patterns for writing tests in the FastAPI Core API. A key principle we want to abide by is to create fewer, high quality tests. We do not need to aim for 100% test coverage.

_IMPORTANT_ Make sure to write tests that test for behavior, not implementation.

> **📖 Frontend E2E Testing:** This guide focuses on **backend testing** with pytest. For frontend E2E testing patterns with Playwright, see [Frontend E2E Testing Guide](./frontend-e2e-testing.md).

## TL;DR - Quick Reference

**Testing Distribution:** 70% E2E, 20% Integration, 10% Unit

| Test Type | How to Write | When to Use |
|-----------|--------------|-----------|
| **E2E (70%)** | `await client.post("/api/v1/endpoint", json=payload)` | All user-facing features via HTTP |
| **Integration (20%)** | `service = MyService(db_transaction); result = await service.method()` | Service coordination, no HTTP needed |
| **Unit (10%)** | `result = pure_function(input); assert result == expected` | Algorithms, validation logic, calculations |

**Key Principle:** When in doubt, write an E2E test. E2E tests validate the complete stack (HTTP → Router → Service → Database) and are more resilient to refactoring than unit tests.

---

## 🤖 Testing Philosophy for AI-Assisted Development

**E2E Tests Are Your Primary Line of Defense**

When building with AI assistance, prioritize end-to-end tests over unit tests. Here's why:

```
Traditional Manual Dev          AI-Assisted Development
      Unit (70%)                      Unit (10%)
   Integration (20%)              Integration (20%)
      E2E (10%)                       E2E (70%)
```

### Why E2E-First with AI?

- ✅ **Integration is where bugs hide**: AI can write individual components quickly, but the real complexity is in how they integrate
- ✅ **Test the complete stack**: E2E tests validate HTTP → Router → Service → Database, catching architectural mismatches
- ✅ **Resilient to refactoring**: Tests behavior (the contract), not implementation (how it works), so they survive code changes
- ✅ **Real user journeys**: E2E tests validate what actually matters - the complete user experience
- ✅ **Less flaky**: Fewer dependencies means fewer things to mock, fewer reasons for tests to break

### Testing Strategy: 70% E2E, 20% Integration, 10% Unit

**E2E Tests (70%)**: All critical user-facing features via HTTP
- Make actual HTTP POST/GET/PUT requests to endpoints
- Use `client: AsyncClient` fixture for full stack testing
- Verify HTTP status codes, response bodies, and database state
- Validate complete workflows from user perspective

```python
async def test_user_journey_via_http(client: AsyncClient, db_transaction: AsyncSession):
    # Make actual HTTP request through full stack
    response = await client.post("/api/v1/endpoint", json=payload)

    # Verify HTTP contract
    assert response.status_code == 200
    assert response.json()["key"] == "value"

    # Verify database state changed
    result = await db_transaction.execute(select(Model).where(...))
    obj = result.scalar_one()
    assert obj.field == expected_value
```

**Integration Tests (20%)**: Service coordination without HTTP layer
- Call service layer directly when HTTP layer is irrelevant
- Test complex orchestration between services
- Validate error handling and compensation patterns
- Used when testing internal business logic flows

```python
async def test_service_coordination(db_transaction: AsyncSession):
    service = MyService(db_transaction)
    result = await service.complex_operation(input_data)
    assert result.success is True
```

**Unit Tests (10%)**: Critical algorithms and complex business rules only
- Test pure business logic functions
- Validate complex validation rules
- Test mathematical calculations or algorithms
- Mock external dependencies

```python
def test_business_rule_calculation():
    result = calculate_discount(price=100, customer_type="premium")
    assert result == 80  # 20% discount
```

## E2E vs Integration Tests: Clear Definitions

### E2E Tests (Test via HTTP)
E2E tests make **actual HTTP POST/GET/PUT requests** through the full stack:

```
┌─────────────┐
│ Test Code   │
│   (client)  │
└──────┬──────┘
       │ HTTP POST request
       ▼
┌─────────────────────────────────┐
│   FastAPI Router                │
│ - Route matching                │
│ - Authentication/Authorization  │
│ - Request parsing               │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Service Layer                 │
│ - Business logic                │
│ - Database operations           │
│ - External API calls            │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Database                      │
│ - Data persistence              │
│ - Transactions                  │
└─────────────────────────────────┘
```

**Pattern**:
```python
async def test_webhook_triggers_sync(client: AsyncClient, db_transaction: AsyncSession):
    # ARRANGE: Setup test data
    org = OrganizationFactory.create()
    await db_transaction.flush()

    contact = ContactFactory.create(organization_id=org.id)
    await db_transaction.flush()

    # ACT: Make actual HTTP request
    response = await client.post(
        "/api/v1/retell/webhook",
        json=webhook_payload
    )

    # ASSERT: Verify HTTP response
    assert response.status_code == 200

    # ASSERT: Verify database state
    result = await db_transaction.execute(select(Contact).where(...))
    synced_contact = result.scalar_one()
    assert synced_contact.status == "synced"
```

### Integration Tests (Call Service Directly)
Integration tests call the **service layer directly**, bypassing HTTP routing:

```python
async def test_service_coordinates_operations(db_transaction: AsyncSession):
    # ARRANGE: Setup
    service = MyService(db_transaction)

    # ACT: Call service method directly
    result = await service.complex_operation(input_data)

    # ASSERT: Verify result
    assert result.success is True
```

### Key Differences

| Aspect | E2E Test | Integration Test |
|--------|----------|------------------|
| **How called** | HTTP POST/GET/PUT via `client` | Direct service method call |
| **What it tests** | Complete HTTP stack | Service logic without HTTP |
| **Tests** | Routing, parsing, serialization, business logic | Business logic only |
| **Catches** | Route mismatches, serialization errors, auth bugs | Business logic bugs |
| **Use when** | Testing user-facing features | Testing internal orchestration |
| **Fixture** | `client: AsyncClient` | `db_transaction: AsyncSession` |

### Examples from Codebase

**Before (Integration Test - calls service directly)**:
```python
# ❌ This is integration, not e2e
service = GHLSyncService(db_transaction)
result = await service.sync_call_to_ghl(call_log, contact)
assert result is True
```

**After (E2E Test - uses HTTP)**:
```python
# ✅ This is true e2e - makes HTTP request
response = await client.post(
    "/api/v1/retell/webhook",
    json=call_analyzed_webhook
)
assert response.status_code == 200

# Verify sync happened by checking database
synced_contact = await db_transaction.get(Contact, contact.id)
assert synced_contact.custom_fields.get("ghl_contact_id") is not None
```

## Quick Start

```bash
# Run all tests
pytest

# Run specific tests
pytest tests/auth/ -v
pytest tests/organizations/test_service.py::test_create_organization -v

# Run with coverage
pytest --cov=app --cov-report=html
```

## Factory-boy Best Practices

### Core Philosophy

**Factory-boy creates objects in memory, tests control persistence.**

```python
from tests.factories import UserFactory, OrganizationFactory, OrganizationMemberFactory

# ✅ GOOD - Explicit, predictable
org = OrganizationFactory.create()        # Creates in memory
user = UserFactory.create()              # Creates in memory
await db_transaction.commit()             # Persists when needed

# ❌ AVOID - Hidden side effects
user = UserFactory.create(with_magic=True)  # Don't create complex hooks
```

### Explicit 3-Object Pattern (Recommended)

For creating users with organization membership:

```python
async def test_user_permissions(db_transaction):
    # Each factory creates one object
    org = OrganizationFactory.create()
    user = UserFactory.create(
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        primary_org_id=org.id,
    )
    member = OrganizationMemberFactory.create(
        user_id=user.id,
        organization_id=org.id,
        role="admin"
    )

    # Commit only when test needs persistent objects
    await db_transaction.commit()  # For refresh/query operations

    assert user.primary_org_id == org.id
    assert member.role == "admin"
```

### When to Commit in Tests (Updated Pattern)

**CRITICAL**: The `db_transaction` fixture maintains isolation by rolling back all changes. While `commit()` calls are handled gracefully, prefer patterns that don't require explicit commits.

```python
async def test_example(db_transaction):
    user = UserFactory.create()

    # ✅ No commit needed for object property tests
    assert user.email.endswith("@example.com")  # Works without commit

    # ✅ PREFERRED: Use flush() for object IDs without breaking isolation
    await db_transaction.flush()  # Gets object IDs without committing
    await db_transaction.refresh(user)  # Now refresh works

    # ⚠️  Commit when absolutely necessary (handled by fixture, but less ideal)
    # await db_transaction.commit()  # Use only when service requires persistence

    # ✅ Most service queries work with flushed objects
    service = UserService(db_transaction)
    result = await service.find_by_email(user.email)  # Works after flush()
```

**Preferred Pattern**: Use `flush()` instead of `commit()` to get object IDs while maintaining transaction isolation.

### Two-Stage Flush Pattern for Foreign Key Dependencies (Updated)

When creating objects with foreign key relationships, use the two-stage flush pattern to avoid session mismatch issues while maintaining isolation:

```python
async def authenticated_client_with_retell(client, db_transaction):
    """Example fixture using two-stage flush pattern"""

    # STAGE 1: Create foundation objects first
    org = OrganizationFactory.create()
    user = UserFactory.create(primary_org_id=org.id)
    member = OrganizationMemberFactory.create(user_id=user.id, organization_id=org.id)

    # Flush foundation objects first to get IDs
    await db_transaction.flush()

    # STAGE 2: Create dependent objects after foundations have IDs
    retell_config = RetellConfigurationFactory.create(organization_id=org.id)

    # Final flush for all objects (optional - can use commit() if service requires persistence)
    await db_transaction.flush()

    return client
```

**When to use**: When creating objects that reference other objects via foreign keys, especially in fixtures.

**Why flush() is better**: Objects get database IDs and can reference each other, but changes remain isolated to the test transaction and auto-rollback on test completion.

**Note**: Use `commit()` only when the service being tested specifically requires committed/persistent objects (rare).

## Test Organization and Colocation

### Core Principle

**`tests/` = Infrastructure** (factories, fixtures, global conftest)
**`app/features/*/tests/` = Logic** (actual test files)

Think of `tests/` as a utilities library you import from, not a place to write tests.

### What Lives Where

**`tests/` (Infrastructure)**:

- ✅ `factories.py` - All Factory-boy definitions
- ✅ `fixtures/` - JSON fixtures, production webhook captures
- ✅ `conftest.py` - Global pytest fixtures (db_transaction, etc.)
- ✅ `core/` - Infrastructure tests (database, auth, migrations)
- ❌ NO `test_*.py` files for features

**`app/features/*/tests/` (Test Logic)**:

- ✅ `test_*.py` - Actual test files
- ✅ `conftest.py` - Imports from `tests/conftest.py` explicitly
- ❌ NO factories or fixtures (import from `tests/`)

### Directory Structure

```
servers/core-api/
├── tests/                          # Infrastructure
│   ├── conftest.py                 # Global fixtures
│   ├── factories.py                # All factories (shared)
│   ├── fixtures/                   # JSON fixtures (shared)
│   └── core/                       # Infrastructure tests only
│
└── app/features/                   # Test logic
    ├── tests/                      # Cross-feature integration
    │   ├── conftest.py             # from tests.conftest import ...
    │   └── test_complete_call_flow.py
    ├── retell/webhooks/tests/      # Feature-specific
    └── contacts/tests/
```

### Colocated conftest.py Pattern

```python
# app/features/tests/conftest.py
from tests.conftest import db_transaction, test_engine
from tests.factories import OrganizationFactory, RetellConfigurationFactory
```

**Benefits**: Explicit imports, clear dependencies, self-documenting.

### Decision Tree: Where Should My Test Live?

**New tests** (always colocate):

1. **Infrastructure test** (database, auth, migrations)?
   → `tests/core/` or `tests/infrastructure/`

2. **Cross-feature integration** (spans multiple features)?
   → `app/features/tests/`

3. **Single feature** (multiple submodules)?
   → `app/features/<feature>/tests/`

4. **Single submodule** (focused)?
   → `app/features/<feature>/<submodule>/tests/`

**Existing tests** (legacy):

- See `tests/LEGACY_TESTS.md` for migration plan
- Keep infrastructure tests in `tests/core/`
- Migrate feature tests when touching related code

### Test Quality Standards

#### Gold Standard: Fixture-Based Integration Tests

The highest quality tests use real webhook/function fixtures captured from production:

```python
# app/features/tests/test_complete_call_flow.py
def test_contact_enrichment(db_transaction):
    # Load REAL webhook from production
    call_started = CallStartedEvent(**load_webhook_fixture("call_started.json"))

    # Test with production data
    await process_webhook(org.id, call_started, db_transaction)

    # Verify behavior
    assert contact.name == "Expected Name"
```

**Benefits:**

- ✅ Tests actual production data structures
- ✅ Catches schema mismatches early
- ✅ High confidence in production behavior
- ✅ Documents real-world scenarios

#### Unit Tests (Colocated)

Fast, focused tests for specific logic:

```python
# app/features/retell/webhooks/tests/test_schemas.py
def test_call_started_schema_validation():
    payload = {"event": "call_started", ...}
    event = CallStartedEvent(**payload)
    assert event.call.direction == "inbound"
```

### Test Code Quality

Tests should be **clean** but not **strictly typed**:

**DO enforce:**

- ✅ Consistent formatting (ruff format)
- ✅ Proper imports (ruff check)
- ✅ Clear naming and structure

**DON'T enforce:**

- ❌ Strict type annotations (mypy)
- ❌ Every parameter annotated
- ❌ Complex type gymnastics for fixtures

**Why?** Tests use dynamic patterns (fixtures, mocks, factories) where strict typing adds friction without benefit.

### Migration Strategy

**For legacy tests in `tests/`:**

1. **Don't mass-migrate** - move incrementally
2. **When touching code** - migrate related tests
3. **Document status** - track in `tests/LEGACY_TESTS.md`
4. **Infrastructure stays** - database, auth, migrations keep their location

**For new tests:**

- ✅ Always colocate from day 1
- ✅ Follow decision tree above
- ✅ Use fixture-based integration tests when possible

## Available Factory Traits

### OrganizationFactory

```python
OrganizationFactory(minimal=True)           # Minimal org for onboarding
OrganizationFactory(with_business_hours=True)  # Business hours configured
OrganizationFactory(with_calendar=True)     # Cal.com integration
OrganizationFactory(fully_configured=True)  # All settings configured
```

### UserFactory

```python
UserFactory(admin=True)                     # Admin user, fully onboarded
UserFactory(onboarded=True)                 # Regular onboarded user
UserFactory(onboarding_new=True)            # New user, no profile
UserFactory(onboarding_profile_done=True)   # Profile completed
UserFactory(onboarding_org_done=True)       # Organization info completed
UserFactory(onboarding_complete=True)       # Fully onboarded user
```

### OrganizationMemberFactory

```python
OrganizationMemberFactory(owner=True)       # Owner role
OrganizationMemberFactory(admin=True)       # Admin role
OrganizationMemberFactory(viewer=True)      # Viewer role
OrganizationMemberFactory(inactive=True)    # Inactive membership
```

### RetellConfigurationFactory

```python
RetellConfigurationFactory(with_voice_agent=True)  # Voice agent configured
RetellConfigurationFactory(with_phone_number=True) # Phone number added
RetellConfigurationFactory(complete=True)          # Full configuration
```

## Authentication Patterns

### Pre-configured Clients

```python
# Basic authenticated client
async def test_auth_required(authenticated_client):
    response = await authenticated_client.get("/api/v1/me")
    assert response.status_code == 200

# Provider with organization context
async def test_provider_workflow(authenticated_provider_client):
    response = await authenticated_provider_client.get("/api/v1/dashboard")
    assert response.status_code == 200
```

### Custom Auth Scenarios

```python
async def test_admin_permissions(client, db_transaction):
    # Create admin user using explicit 3-object pattern
    org = OrganizationFactory.create()
    admin_user = UserFactory.create(admin=True, primary_org_id=org.id)
    member = OrganizationMemberFactory.create(
        user_id=admin_user.id,
        organization_id=org.id,
        role="admin"
    )
    await db_transaction.commit()

    # Override auth dependency
    from app.core.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: admin_user

    response = await client.get("/api/v1/admin/settings")
    assert response.status_code == 200

    app.dependency_overrides.pop(get_current_user, None)  # Cleanup
```

### Unified Fixture Pattern (Recommended)

Create self-contained fixtures that own all their data instead of depending on multiple fixtures:

```python
# ✅ GOOD - Single unified fixture
@pytest.fixture
async def authenticated_client_with_retell(client, db_transaction):
    """Independent fixture creates complete test environment"""
    # Creates org + user + member + retell_config
    # All in one coherent fixture using two-stage commit

    org = OrganizationFactory.create()
    user = UserFactory.create(primary_org_id=org.id)
    member = OrganizationMemberFactory.create(user_id=user.id, organization_id=org.id)
    await db_transaction.commit()

    retell_config = RetellConfigurationFactory.create(organization_id=org.id)
    await db_transaction.commit()

    # Set up auth and store references
    app.dependency_overrides[get_current_user] = lambda: user
    client.test_user = user
    client.test_org = org
    client.test_retell_config = retell_config

    yield client
    app.dependency_overrides.pop(get_current_user, None)

# ❌ AVOID - Multi-fixture dependencies
async def test_problematic(authenticated_client, org_with_retell):
    # These fixtures create different organizations!
    # Leads to session mismatch and foreign key violations
    pass
```

**Benefits**:

- Eliminates session mismatches
- Ensures complete test isolation
- Makes test intentions clearer
- Prevents foreign key constraint violations

**When to use**: For integration tests that need multiple related objects.

## Infrastructure Fixtures

Keep these for test infrastructure:

```python
# Database isolation - each test gets clean transaction
async def test_example(db_transaction):
    user = UserFactory()  # Automatically uses db_transaction
    await db_transaction.commit()  # Persist if needed
    # Transaction auto-rolls back after test

# HTTP client with database injection
async def test_api_endpoint(client):
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
```

## SOC2 Compliance Checklist

All tests involving sensitive business data must include:

- ✅ **Access Control**: Verify role-based permissions
- ✅ **Audit Logging**: Ensure all sensitive data access is logged
- ✅ **Data Encryption**: Verify sensitive fields are encrypted
- ✅ **Multi-tenant Isolation**: Ensure data segregation between organizations

## Common Patterns

### Multiple Related Objects

```python
async def test_organization_workflow(db_transaction):
    org = OrganizationFactory(with_business_hours=True)
    admin = UserFactory(admin=True, primary_org_id=org.id)
    member = UserFactory(onboarded=True, primary_org_id=org.id)

    # Create memberships explicitly
    admin_membership = OrganizationMemberFactory.create(
        user_id=admin.id, organization_id=org.id, role="admin"
    )
    member_membership = OrganizationMemberFactory.create(
        user_id=member.id, organization_id=org.id, role="member"
    )

    await db_transaction.commit()  # Persist for test queries
```

### Transaction Isolation

```python
async def test_user_creation(db_transaction):
    user1 = UserFactory(email="user1@test.com")
    user2 = UserFactory(email="user2@test.com")

    # Both users exist in this test's transaction
    # But are automatically cleaned up after test completes
```

## Testing External Integrations

**Features**: Mock integration clients directly (no dependency injection needed)

```python
# Simple mocking - no ports/adapters complexity
from unittest.mock import patch

@pytest.fixture
def mock_retell():
    with patch('app.features.voice_agents.service.RetellClient') as mock:
        mock.return_value.create_agent.return_value = {"agent_id": "test-123"}
        yield mock

@pytest.fixture
def mock_calcom():
    with patch('app.features.appointments.service.CalComClient') as mock:
        mock.return_value.create_booking.return_value = {"id": "booking-456"}
        yield mock

def test_create_agent_with_booking(mock_retell, mock_calcom):
    service = VoiceAgentService()  # No DI - service creates its own dependencies
    result = await service.create_agent_with_booking(test_config, db_session)

    # Verify integration calls
    mock_calcom.return_value.create_booking.assert_called_once()
    mock_retell.return_value.create_agent.assert_called_once()
    assert result.agent_id == "test-123"
```

**Why This Testing Approach Works:**

- ✅ **No dependency injection complexity** - services create their own integration clients
- ✅ **Simple mocking** - just patch the import path
- ✅ **Fast tests** - no container or complex setup
- ✅ **Maintainable** - tests break only when contracts change, not implementation details

**Integration Tests**: Test against sandbox APIs or recorded responses

```python
# Integration tests with real (sandbox) APIs
async def test_retell_client_create_agent():
    client = RetellClient()  # Uses test API keys
    result = await client.create_agent({"name": "Test Agent"})
    assert result["agent_id"] is not None
```

## Testing Three-Layer Architecture

### Layer 1: Router Testing

Test HTTP concerns only, mock service layer:

```python
def test_create_voice_agent_success():
    with patch('app.features.voice_agents.router.get_voice_agent_service') as mock_service:
        mock_service.return_value.create_agent.return_value = {"success": True, "agent_id": "test-123"}

        response = client.post("/api/voice-agents", json={"name": "Test Agent"})

        assert response.status_code == 200
        assert response.json()["agent_id"] == "test-123"
        mock_service.return_value.create_agent.assert_called_once()
```

### Layer 2: Orchestrator Testing

Test coordination logic, mock specialized services:

```python
@pytest.fixture
def voice_agent_service():
    with patch('app.features.voice_agents.service.VoiceAgentCreationService') as mock:
        service = VoiceAgentService()
        service.creation_service = mock.return_value
        return service

async def test_orchestration(voice_agent_service):
    voice_agent_service.creation_service.create_agent.return_value = {
        "success": True, "agent_id": "test-123"
    }

    result = await voice_agent_service.create_agent("org-123", request)

    assert result.success is True
    voice_agent_service.creation_service.create_agent.assert_called_once()
```

### Layer 3: Specialized Service Testing

Test business logic, mock external integrations:

```python
async def test_specialized_service(creation_service):
    creation_service._api_client.create_agent.return_value = Mock(agent_id="test-123")

    result = await creation_service.create_agent(flow_id="flow-456", name="Test")

    assert result["success"] is True
    assert result["agent_id"] == "test-123"
```

## Testing Compensation Patterns

**Testing External API Cleanup**:

```python
async def test_compensation_pattern_cleanup():
    with patch('app.integrations.retell.client.RetellClient') as mock_retell:
        service = VoiceAgentService()

        # Mock partial success scenario
        mock_retell.return_value.create_conversation_flow.return_value = {"conversation_flow_id": "flow-123"}
        mock_retell.return_value.create_agent.side_effect = Exception("Agent creation failed")

        # Track cleanup calls
        cleanup_calls = []
        mock_retell.return_value.delete_conversation_flow.side_effect = lambda flow_id: cleanup_calls.append(f"delete_flow_{flow_id}")

        # Test the operation
        result = await service.create_complete_call_system(test_request, "org-123", mock_db)

        # Verify failure and cleanup
        assert result.success is False
        assert "Agent creation failed" in result.message
        assert "delete_flow_flow-123" in cleanup_calls

        # Verify cleanup was called
        mock_retell.return_value.delete_conversation_flow.assert_called_once_with("flow-123")
```

## Frontend Testing Patterns

**Frontend Tests**: Test component integration with API services

```typescript
// BusinessInformation.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import BusinessInformation from './BusinessInformation';

const server = setupServer(
  rest.put('/api/voice-agents/:id', (req, res, ctx) => {
    return res(ctx.json({ success: true, message: 'Updated successfully' }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test('updates agent configuration successfully', async () => {
  render(<BusinessInformation agentId="test-123" />);

  // User interaction
  fireEvent.change(screen.getByLabelText('Agent Name'), {
    target: { value: 'New Agent Name' }
  });
  fireEvent.click(screen.getByText('Save Changes'));

  // Verify success feedback
  await waitFor(() => {
    expect(screen.getByText('Updated successfully')).toBeInTheDocument();
  });
});

test('handles API failure gracefully', async () => {
  server.use(
    rest.put('/api/voice-agents/:id', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'Server error' }));
    })
  );

  render(<BusinessInformation agentId="test-123" />);

  fireEvent.change(screen.getByLabelText('Agent Name'), {
    target: { value: 'New Agent Name' }
  });
  fireEvent.click(screen.getByText('Save Changes'));

  await waitFor(() => {
    expect(screen.getByText(/error/i)).toBeInTheDocument();
  });
});
```

**Stack:** Jest + React Testing Library + MSW + React Query testing utilities

### Mocking React Query Hooks

When testing components that use React Query hooks (or other hooks with complex return types), use type-safe casting to avoid `any` types:

```typescript
// ✅ Recommended: Type-safe and pragmatic
import { useCalls } from '../hooks/useCalls';

// Note: useCalls uses React Query which has a complex return type.
// We use 'as unknown as ReturnType<typeof useCalls>' for test mocks
// since we only need to mock the properties the component actually uses.

vi.mocked(useCalls).mockReturnValue({
  data: {
    calls: mockCalls,
    total: mockCalls.length,
    hasMore: false,
  },
  isLoading: false,
  error: null,
  refetch: vi.fn(),
  // Only mock properties the component actually uses
} as unknown as ReturnType<typeof useCalls>);

// ❌ Avoid: Using 'any' breaks type safety
vi.mocked(useCalls).mockReturnValue({
  data: mockData,
} as any); // ESLint error: no-explicit-any
```

**Why this pattern:**

- **Type-safe**: Uses the actual hook's return type via `ReturnType<typeof>`
- **Pragmatic**: Doesn't require mocking 20+ unused React Query properties
- **Maintainable**: Test breaks if hook signature changes, catching bugs early
- **Industry standard**: Recommended by Vitest/TypeScript communities for complex types

**When to use:**

- React Query hooks (useQuery, useMutation, custom hooks wrapping them)
- Any hook with complex return types (10+ properties)
- Third-party hooks with extensive interfaces

**Alternative approaches and why they fail:**

- `Partial<ReturnType<typeof>>` - TypeScript still requires all nested required properties
- Custom interface matching hook - Brittle, duplicates type definition, breaks on updates
- Mocking all properties - Verbose, error-prone, hard to maintain

## Schema Validation and Testing

### Pydantic Schema Testing

Create response objects directly, don't validate mocks:

```python
# ✅ Create directly
response = TrainingFileListResponse(files=[TrainingFileResponse(id=file.id, filename=file.filename)])

# ❌ Avoid validating mocks
response = TrainingFileResponse.model_validate(mock_file)  # Brittle
```

### TypeScript Mock Compatibility

Include all required fields in test mocks:

```typescript
const mockStatus: GoogleCalendarStatus = {
  connected: false,
  message: 'Not connected',
  needsReauth: false,
  tokenExpired: false, // Don't forget new fields
};
```

### Schema Evolution

Test minimal and full field sets:

```python
def test_schema_backward_compatibility():
    minimal = UserResponse(id="test-123", organization_id="org-456", created_at=datetime.utcnow())
    assert minimal.id == "test-123"

def test_schema_with_optional_fields():
    full = UserResponse(id="test-123", metadata={"key": "value"}, **minimal_data)
    assert full.metadata["key"] == "value"
```

## Testing Best Practices

### What to Test at Each Layer

**Router Layer (Thin)**:

- HTTP status codes
- Request/response serialization
- Authentication/authorization
- Service delegation

**Orchestrator Layer (Coordination)**:

- Service composition
- Error handling and transformation
- Business workflow logic
- Compensation patterns

**Specialized Service Layer (Domain Logic)**:

- Business rules and validation
- External API integration
- Data transformation
- Error handling

**Integration Layer (External APIs)**:

- API client configuration
- Error handling and retries
- Response normalization
- Sandbox/test environment integration

### Testing Anti-Patterns to Avoid

❌ **Over-mocking**: Don't mock every dependency, focus on boundaries
❌ **Testing implementation details**: Test behavior, not internal methods
❌ **Complex test setup**: Keep test data and mocking simple
❌ **Integration test overuse**: Use unit tests for business logic, integration tests for workflows
❌ **Snapshot testing overuse**: Only for stable UI components, not for business logic

### Testing Strategy Summary (AI-Assisted Development)

1. **E2E Tests (70%)**: All critical user-facing features via HTTP endpoints
   - Use `client: AsyncClient` fixture to make real HTTP requests
   - Validate complete workflows: HTTP → Router → Service → Database
   - Test behavioral contracts, not implementation details
   - Most resilient to refactoring

2. **Integration Tests (20%)**: Service coordination and complex orchestration
   - Call service layer directly when HTTP layer is irrelevant
   - Test compensation patterns and error handling
   - Used for internal business logic flows
   - Faster feedback than E2E for specific service interactions

3. **Unit Tests (10%)**: Critical algorithms and complex business rules
   - Pure functions and mathematical calculations
   - Complex validation logic
   - Fast, isolated tests with minimal dependencies

**Key Principles for AI-Assisted Development**:

- **Prioritize E2E**: AI writes components fast, but integration is where bugs hide
- **Test through HTTP**: Use `client: AsyncClient` for full-stack validation
- **Verify database state**: E2E tests should check that side effects persisted correctly
- **Mock external APIs**: Use VCR cassettes or mocks for third-party integrations
- **Write fewer tests**: 10 high-quality E2E tests beat 50 weak unit tests
- **Test behavior, not implementation**: Tests should survive refactoring

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running
- Verify test database `stello_test` exists
- Check `.env` file has correct `DATABASE_URL`

### Common Async Test Issues

- Use `@pytest.mark.asyncio` decorator
- Use `async def` for test methods
- Ensure `pytest-asyncio` is installed

### Factory Issues

- **"Instance not persistent"**: Add `await db_transaction.commit()` before refresh
- **"Ambiguous foreign key"**: Use explicit join conditions in queries
- **"Invalid trait"**: Check trait names match factory definitions

### Database Transaction Isolation Issues

**Symptoms**:

- `duplicate key value violates unique constraint "pg_type_typname_nsp_index"`
- Schema changes persisting between tests
- Foreign key constraint violations with `organization_id` not found

**Root Causes**:

1. **Transaction Isolation Breakdown**: Tests calling `commit()` bypass rollback mechanism
2. **Schema Pollution**: Committed schema changes accumulate across test runs
3. **Session Mismatches**: Objects created in different fixtures/sessions trying to reference each other

**Solutions**:

1. **Use `flush()` instead of `commit()`** for getting object IDs while maintaining isolation
2. **Use unified fixtures** with two-stage flush pattern instead of multi-fixture dependencies
3. **The `db_transaction` fixture now handles committed transactions** by forcing rollback to maintain isolation

```python
# ❌ PROBLEMATIC - Different sessions
async def test_bad(authenticated_client, org_with_retell):
    # authenticated_client creates Org A
    # org_with_retell creates Org B
    # RetellConfig tries to reference Org B but session only knows about Org A
    pass

# ✅ FIXED - Single session
async def test_good(authenticated_client_with_retell):
    # Single fixture creates org + user + retell_config in coherent sequence
    pass
```

## Contributing Guidelines

When adding new tests:

1. **Follow explicit 3-object pattern** for user + organization setup
2. **Use factory traits** instead of custom post-generation hooks
3. **Test both success and failure cases**
4. **Include SOC2 compliance checks** for sensitive data operations
5. **Use descriptive test names** that explain what is being tested
6. **PREFER `flush()` over `commit()`** to maintain test isolation while getting object IDs
7. **Use unified fixtures** instead of multi-fixture dependencies to avoid session mismatches
8. **Apply two-stage flush pattern** when creating objects with foreign key dependencies
9. **Only use `commit()` when the service absolutely requires persistent objects** (handled gracefully by fixture but less ideal)
