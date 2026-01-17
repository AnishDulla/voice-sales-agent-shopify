# Third-Party Integration Development Workflow

Complete guide for adding new external API integrations (Twilio, Stripe, Cal.com, etc.) with the right balance of development speed, testing confidence, and cost management.

## TL;DR - The Workflow

```
Phase 1: Development (Mocks)     → Phase 2: Testing (Mocks)     → Phase 3: Validation (VCR)     → Phase 4: Production (Real APIs)
├─ Set up MSW mocks (frontend)   ├─ Write E2E tests            ├─ Record cassette once      ├─ Remove mock overrides
├─ Set up @patch (backend)       ├─ Write integration tests    ├─ Validate API contract    └─ Deploy with credentials
├─ Rapid iteration locally       ├─ Run tests with mocks       └─ Replay cassette forever
├─ No credentials needed         └─ No API costs, no rate limits  (CI/CD, staging, prod)
└─ Fast feedback loop
```

**Key Question Answered**: "Do I set up mocks first, then switch to production APIs?"
- ✅ **Yes, exactly.** Start with mocks for fast development, write tests with mocks (no costs), record one cassette for validation, deploy with real APIs.
- ✅ **This is industry standard** used by Google, Stripe, AWS, Twilio, etc.

---

## Quick Reference

### Configuration (Smart Defaults - No Setup Needed!)

```bash
# Mocks enabled automatically in development/test
ENVIRONMENT=development npm run dev    # ✅ Uses mocks
ENVIRONMENT=test pytest                # ✅ Uses mocks

# Real APIs enabled automatically in staging/production
ENVIRONMENT=staging                    # ✅ Uses real APIs
ENVIRONMENT=production                 # ✅ Uses real APIs
```

### Add Mock Support to New Service (Template)

1. **Create mock client** in `app/integrations/[service]/mocks.py`:
   ```python
   class Mock[Service]Client:
       def operation(self, ...): return {"id": "mock-123"}
   ```

2. **Update factory** in `app/integrations/[service]/client.py`:
   ```python
   import os

   def get_[service]_client():
       """Get client based on environment."""
       environment = os.getenv("ENVIRONMENT", "development").lower()
       is_test = environment == "test" or os.getenv("PYTEST_CURRENT_TEST") is not None

       if is_test:
           from app.integrations.[service].mocks import Mock[Service]Client
           return Mock[Service]Client()

       # For services with mock/test API support (like Twilio)
       use_mock_api = environment in ("development", "staging")
       return [Service]Client(use_mock_api=use_mock_api)
   ```

3. **That's it!** Environment detection handles the rest automatically.

---

## Phase 1: Development with Mocks

When first adding an integration, use mocks for rapid iteration without credentials or API costs.

### Frontend: Mock with Mock Service Worker (MSW)

MSW intercepts HTTP requests before they reach the network:

```typescript
// clients/web_portal/src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  // Mock Twilio SMS registration endpoints
  http.post('*/sms/registration/brand', async () => {
    return HttpResponse.json({
      customer_profile_sid: 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
      brand_registration_sid: 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
      status: 'submitted',
      message: 'Brand registration submitted. Awaiting carrier approval (typically 1-2 weeks).',
    });
  }),

  http.post('*/sms/registration/campaign', async () => {
    return HttpResponse.json({
      campaign_sid: 'TCXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
      service_sid: 'MGXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
      status: 'verified',
      message: 'Campaign submitted for carrier verification (typically 1-3 business days).',
    });
  }),

  http.get('*/sms/registration/status', async () => {
    return HttpResponse.json({
      organization_id: 'org-123',
      brand_registered: true,
      brand_sid: 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
      brand_status: 'approved',
      campaigns: [
        {
          id: 'TCXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
          use_case: '2FA',
          status: 'verified',
        },
      ],
      next_steps: 'Brand approved! Create campaigns for your use cases',
    });
  }),
];
```

**Setup**: MSW is already configured in `src/mocks/`. Add your handlers here and they'll automatically intercept all matching requests.

**Benefits**:
- ✅ No credentials needed
- ✅ Instant feedback (no API latency)
- ✅ Control response timing and errors
- ✅ Develop offline
- ✅ No rate limiting concerns

### Backend: Mock with `@patch`

Use `unittest.mock.patch` to mock the integration client:

```python
# app/features/sms/registration/tests/test_service.py
from unittest.mock import patch, AsyncMock
import pytest

@pytest.mark.asyncio
async def test_brand_registration_workflow(db_transaction):
    """Mock-based test for rapid development"""

    # Mock the Twilio client
    with patch('app.integrations.twilio.client.AsyncTwilioClient') as mock_client:
        # Setup mock responses
        mock_client.return_value.create_customer_profile.return_value = {
            'customer_profile_sid': 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
        }
        mock_client.return_value.submit_brand_registration.return_value = {
            'brand_registration_sid': 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            'status': 'submitted',
        }

        # Test your service
        service = TwilioRegistrationService(db_transaction)
        result = await service.submit_brand_registration(
            org_id='org-123',
            brand_type='trusted_unverified'
        )

        assert result['brand_registration_sid'] == 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
        assert result['status'] == 'submitted'
```

**Where to patch**: Mock at the integration layer, not the SDK. This maintains thin wrapper contracts:

```python
# ✅ CORRECT: Mock the integration client
with patch('app.integrations.twilio.client.TwilioRegistrationClient'):
    pass

# ❌ WRONG: Mocking the SDK directly breaks the abstraction
with patch('twilio.rest.Client'):
    pass
```

**Benefits**:
- ✅ No API calls in tests
- ✅ Control any response scenario (success, failure, edge cases)
- ✅ Tests run instantly
- ✅ Deterministic (no flaky rate limit issues)

### Development Workflow Example

Here's what development with mocks looks like:

```python
# Step 1: Define what you're building
# app/integrations/twilio/client.py
class TwilioRegistrationClient:
    async def create_customer_profile(self, org_id: str, friendly_name: str) -> dict:
        """Create Trust Hub customer profile"""
        # TODO: Implement
        raise NotImplementedError

# Step 2: Write a test with a mock
# app/features/sms/registration/tests/test_service.py
@pytest.mark.asyncio
async def test_create_customer_profile():
    with patch('app.integrations.twilio.client.TwilioRegistrationClient') as mock:
        mock.return_value.create_customer_profile.return_value = {
            'customer_profile_sid': 'test-sid'
        }

        client = TwilioRegistrationClient()
        result = await client.create_customer_profile('org-123', 'Test Org')

        assert result['customer_profile_sid'] == 'test-sid'

# Step 3: Implement the integration client
# app/integrations/twilio/client.py
class TwilioRegistrationClient:
    async def create_customer_profile(self, org_id: str, friendly_name: str) -> dict:
        try:
            profile = await self.client.trust_products.customer_profiles.create(
                friendly_name=friendly_name,
                email='contact@example.com',
                # ... other fields
            )
            return {
                'customer_profile_sid': profile.sid,
                'status': 'created',
            }
        except TwilioException as e:
            raise ExternalServiceError(f"Failed to create profile: {e}")

# Step 4: Run tests with mock - instant feedback, no API calls
pytest tests/sms/registration/test_service.py -v
```

---

## Phase 2: Testing with Mocks

Write comprehensive tests using mocks. This validates behavior before touching production APIs.

### E2E Tests with Mocks (Frontend)

```typescript
// clients/web_portal/src/features/dashboard/tests/BusinessRegistration.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import BusinessRegistrationFlow from '../components/BusinessRegistrationFlow';

// Setup MSW server
const server = setupServer(
  http.post('*/sms/registration/brand', async ({ request }) => {
    const body = await request.json() as any;

    // Validate request format
    if (!body.friendly_name) {
      return HttpResponse.json(
        { error: 'Missing friendly_name' },
        { status: 400 }
      );
    }

    return HttpResponse.json({
      customer_profile_sid: 'test-profile-sid',
      brand_registration_sid: 'test-brand-sid',
      status: 'submitted',
      message: 'Brand registration submitted.',
    });
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test('user can submit brand registration form', async () => {
  render(<BusinessRegistrationFlow />);

  // User fills out form
  fireEvent.change(screen.getByLabelText('Business Name'), {
    target: { value: 'Acme Corporation' }
  });
  fireEvent.change(screen.getByLabelText('EIN'), {
    target: { value: '12-3456789' }
  });

  // User submits
  fireEvent.click(screen.getByText('Submit Registration'));

  // Verify success message
  await waitFor(() => {
    expect(screen.getByText(/Brand registration submitted/)).toBeInTheDocument();
  });
});

test('displays error when API returns 400', async () => {
  server.use(
    http.post('*/sms/registration/brand', () => {
      return HttpResponse.json(
        { error: 'Invalid business information' },
        { status: 400 }
      );
    })
  );

  render(<BusinessRegistrationFlow />);

  fireEvent.change(screen.getByLabelText('Business Name'), {
    target: { value: '' }  // Invalid: empty
  });
  fireEvent.click(screen.getByText('Submit Registration'));

  await waitFor(() => {
    expect(screen.getByText(/Invalid business information/)).toBeInTheDocument();
  });
});
```

### E2E Tests with Mocks (Backend)

```python
# app/features/sms/registration/tests/test_router.py
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_register_brand_success(authenticated_client: AsyncClient, db_transaction):
    """E2E test: Brand registration via HTTP with mocks"""

    with patch('app.features.sms.registration.service.TwilioRegistrationService') as mock_service:
        # Mock the service to return a brand SID
        mock_instance = AsyncMock()
        mock_instance.create_customer_profile.return_value = {
            'customer_profile_sid': 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
        }
        mock_instance.create_trust_product.return_value = None
        mock_instance.submit_brand_registration.return_value = {
            'brand_registration_sid': 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            'status': 'submitted',
        }
        mock_service.return_value = mock_instance

        # Make actual HTTP request (mocked service layer)
        response = await authenticated_client.post(
            '/api/v1/sms/registration/brand',
            json={
                'friendly_name': 'Test Organization',
                'brand_type': 'trusted_unverified',
            }
        )

        # Verify HTTP response
        assert response.status_code == 201
        assert response.json()['brand_registration_sid'] == 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

        # Verify service was called
        mock_instance.submit_brand_registration.assert_called_once()

@pytest.mark.asyncio
async def test_register_brand_failure_invalid_data(authenticated_client: AsyncClient):
    """E2E test: Validation error handling"""

    response = await authenticated_client.post(
        '/api/v1/sms/registration/brand',
        json={
            # Missing required field
            'brand_type': 'trusted_unverified',
        }
    )

    assert response.status_code == 400
    assert 'friendly_name' in response.json()['detail'].lower()
```

### Integration Tests with Mocks

```python
# app/features/sms/registration/tests/test_service.py
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_brand_registration_compensation_pattern(db_transaction):
    """Integration test: Verify cleanup on failure"""

    with patch('app.integrations.twilio.client.TwilioRegistrationClient') as mock_client:
        # Setup: Partial success (profile created, registration fails)
        mock_instance = AsyncMock()
        mock_instance.create_customer_profile.return_value = {
            'customer_profile_sid': 'BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
        }
        mock_instance.create_trust_product.return_value = None
        mock_instance.submit_brand_registration.side_effect = Exception("Rate limit exceeded")
        mock_instance.delete_customer_profile.return_value = None
        mock_client.return_value = mock_instance

        # Test the service
        service = TwilioRegistrationService(db_transaction)

        # Should fail gracefully and cleanup
        with pytest.raises(Exception):
            await service.submit_brand_registration(
                org_id='org-123',
                brand_type='trusted_unverified'
            )

        # Verify cleanup was called
        mock_instance.delete_customer_profile.assert_called_once()
```

### Testing Benefits

With mocks, you can:
- ✅ **Test error scenarios** - Mock rate limits, timeouts, validation failures
- ✅ **Test edge cases** - Mock unusual API responses
- ✅ **Test compensation patterns** - Verify cleanup on failure
- ✅ **No external dependencies** - Tests run in CI/CD without credentials
- ✅ **Fast feedback** - No API latency, instant results

---

## Phase 3: Pre-Production Validation with VCR.py

Once development and testing are complete, record ONE real API call to validate the contract.

**What is VCR.py?** Video Cassette Recorder for APIs. Records HTTP interactions once, replays forever.

### Record a Cassette (One-Time)

```python
# app/features/sms/registration/tests/test_router_vcr.py
import vcr
from pathlib import Path
import os

# Configure VCR
CASSETTE_DIR = Path(__file__).parent / "cassettes" / "twilio"
twilio_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=os.getenv("VCR_RECORD_MODE", "once"),  # 'once', 'all', 'none'
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["authorization", "x-auth-token"],
    filter_post_data_parameters=["AccountSid", "AuthToken"],  # Redact secrets
    decode_compressed_response=True,
)

@pytest.mark.asyncio
@twilio_vcr.use_cassette("register_brand.yaml")
async def test_register_brand_e2e_vcr(authenticated_client: AsyncClient, db_transaction):
    """E2E test with VCR: Records API call first time, replays forever"""

    # First run with credentials: Records actual Twilio API calls
    # Subsequent runs: Replays from cassette (no credentials needed)
    response = await authenticated_client.post(
        '/api/v1/sms/registration/brand',
        json={
            'friendly_name': 'Test Organization',
            'brand_type': 'trusted_unverified',
            'email': 'test@example.com',
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert 'brand_registration_sid' in data
    assert data['status'] == 'submitted'
```

### Recording Workflow

```bash
# STAGE 1: Development (Mocks Only)
# Run tests with mocks - no credentials needed, instant feedback
pytest tests/sms/registration/test_service.py -v

# STAGE 2: Record Cassette (One-Time, Credentials Required)
# Set Twilio credentials and record
export TWILIO_ACCOUNT_SID=your_account_sid
export TWILIO_AUTH_TOKEN=your_auth_token
export VCR_RECORD_MODE=all

# Run test to record the cassette
pytest tests/sms/registration/test_router_vcr.py::test_register_brand_e2e_vcr -v

# Cassette saved to: tests/sms/registration/cassettes/twilio/register_brand.yaml
# Contains: Request headers, request body, response, timestamps

# STAGE 3: Replay (CI/CD, Staging, Production)
# VCR automatically replays from cassette (default mode: "once")
# No credentials needed, instant response
export VCR_RECORD_MODE=none

pytest tests/sms/registration/test_router_vcr.py -v
```

### Cassette Structure

```yaml
# tests/sms/registration/cassettes/twilio/register_brand.yaml
interactions:
  - request:
      body: |-
        FriendlyName=Test+Organization&Type=verified&Email=test%40example.com
      headers:
        authorization: [REDACTED]  # ← Secrets filtered by VCR
      method: POST
      uri: https://trusthub.twilio.com/v1/CustomerProfiles
    response:
      status:
        code: 201
        message: Created
      headers:
        content-type: [application/json]
      body:
        string: |
          {
            "sid": "BJXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "friendly_name": "Test Organization",
            ...
          }
version: 1
```

**Security**: VCR filters sensitive data before writing to disk.

### When to Record Cassettes

**DO record when:**
- ✅ API contract is stable (SDK versions won't change)
- ✅ Integration is ready for production
- ✅ You have credentials available
- ✅ One real call validates everything needed

**DON'T record when:**
- ❌ Still actively developing the integration
- ❌ SDK contract still changing
- ❌ Waiting for external service to approve credentials

---

## Phase 4: Production Deployment

Once cassettes are recorded, switch to real APIs for production.

### Remove Mock Overrides

```python
# BEFORE: Development with mocks
@pytest.mark.asyncio
async def test_brand_registration():
    with patch('app.integrations.twilio.client.TwilioRegistrationClient') as mock:
        # ... mock implementation

# AFTER: Production with real APIs
@pytest.mark.asyncio
@twilio_vcr.use_cassette("register_brand.yaml")
async def test_brand_registration_vcr():
    # No mock - uses real API call (or cassette replay)
    # ... real implementation
```

### Environment-Based API Selection

Use the factory pattern with environment detection:

```python
# app/integrations/twilio/client.py
import os
from app.core.config import settings

def get_twilio_client() -> "TwilioClient | MockTwilioClient":
    """Get Twilio client based on environment."""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_test = environment == "test" or os.getenv("PYTEST_CURRENT_TEST") is not None

    if is_test:
        from app.integrations.twilio.mocks import MockTwilioClient
        return MockTwilioClient()

    # Real client: use mock API in dev/staging (test credentials)
    use_mock_api = environment in ("development", "staging")
    return TwilioClient(use_mock_api=use_mock_api)

class TwilioClient:
    def __init__(self, use_mock_api: bool = False):
        self._use_mock_api = use_mock_api
        self.client = Client(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
```

See [integration-patterns.md](integration-patterns.md) for the full pattern documentation.

### Deployment Checklist

- ✅ All E2E tests passing with VCR cassettes
- ✅ All integration tests passing with mocks
- ✅ All unit tests passing
- ✅ No mock overrides in production code
- ✅ Credentials available in deployment environment
- ✅ API rate limits and quotas verified
- ✅ Error handling covers API failures
- ✅ Compensation patterns implemented for resource cleanup

---

## Decision Framework

### When Should I Record a VCR Cassette?

| Situation | Decision | Why |
|-----------|----------|-----|
| **Just started integration** | Use mocks only | API contract still unstable, no need to record yet |
| **Finished development, ready to test** | Use mocks for testing | Tests validate behavior without API costs |
| **Integration is stable, ready for production** | Record cassette | Validates real API contract once, replay forever |
| **Deploy to production/staging** | Use VCR replay (no credentials) | Cost-effective, fast, no credentials in test env |
| **Update API integration** | Re-record cassette if contract changes | Captures new API behavior |
| **Multiple environments (dev/staging/prod)** | Record once, use everywhere | Single cassette works across all environments |

### Cost Analysis

```
Development Phase:
├─ Using mocks: $0 (no API calls)
└─ Time: 2-3 days for rapid iteration

Testing Phase:
├─ Using mocks: $0 (no API calls)
└─ Time: 1-2 days writing comprehensive tests

Pre-Production Phase:
├─ Recording cassette: $5-50 (depends on API, typically one successful + few failures to test)
└─ Time: 30 minutes to record and validate

Production Phase:
├─ Using real APIs: Cost depends on usage (you're serving customers now)
└─ Using VCR replay in CI/CD: $0 (replays cassette, no real API calls)
```

**Total Cost to Add Integration**: $5-50 one-time (just to validate the contract), then free forever in testing environments.

---

## Real Example: Twilio A2P SMS Registration

Here's the complete workflow for the A2P SMS feature:

### Phase 1: Development (3-4 hours)

```typescript
// 1. Add MSW handler for frontend
// clients/web_portal/src/mocks/handlers.ts
handlers.push(
  http.post('*/sms/registration/brand', () => {
    return HttpResponse.json({ brand_registration_sid: 'test-sid', status: 'submitted' });
  })
);
```

```python
# 2. Write test with mocked service
# app/features/sms/registration/tests/test_service.py
@pytest.mark.asyncio
async def test_brand_registration_workflow():
    with patch('app.integrations.twilio.client.TwilioRegistrationClient'):
        # ... test logic
```

```python
# 3. Implement integration client
# app/integrations/twilio/client.py
class TwilioRegistrationClient:
    async def submit_brand_registration(self, ...):
        # Actual SDK call here
```

### Phase 2: Testing (2-3 days)

```bash
# Write comprehensive E2E and integration tests
pytest tests/sms/registration/ -v

# All tests use mocks - fast feedback, no API costs
# Tests run in CI/CD without credentials
```

### Phase 3: Validation (30 minutes)

```bash
# Record one cassette with credentials
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
pytest tests/sms/registration/test_vcr.py -v
# Cassette saved: tests/sms/registration/cassettes/twilio/register_brand.yaml
```

### Phase 4: Production (Deployment)

```bash
# Deploy with real credentials
# Remove mock overrides from production code
# VCR replays cassette in CI/CD (no credentials needed)
# Tests validate behavior without extra API costs
```

---

## Best Practices

### 1. Layer Your Mocking

```python
# Unit tests: Mock everything
def test_validation_logic():
    validator = BrandValidator()
    assert validator.is_valid_ein("12-3456789")

# Integration tests: Mock external APIs, use real database
async def test_service_saves_registration():
    with patch('app.integrations.twilio.client.TwilioRegistrationClient'):
        service = TwilioRegistrationService(db)
        # ... test

# E2E tests: Mock external APIs, real HTTP
@twilio_vcr.use_cassette("...")
async def test_full_workflow(client: AsyncClient):
    response = await client.post("/api/v1/sms/registration/brand", ...)
    # ... verify
```

### 2. Use Thin Wrappers

```python
# ✅ Mock the integration client
with patch('app.integrations.twilio.client.TwilioRegistrationClient'):
    pass

# ❌ Don't mock the SDK directly
with patch('twilio.rest.Client'):
    pass
```

Thin wrappers are easier to mock and test.

### 3. Redact Secrets in Cassettes

```python
twilio_vcr = vcr.VCR(
    filter_headers=["authorization", "x-api-key"],
    filter_post_data_parameters=["AccountSid", "AuthToken"],
)
```

VCR automatically redacts sensitive data before writing to disk.

### 4. Version Control Cassettes

Cassettes should be version-controlled (they're just YAML files):

```bash
# Commit cassette to repository
git add tests/sms/registration/cassettes/twilio/register_brand.yaml
git commit -m "record: Twilio A2P brand registration cassette"

# CI/CD replays from version-controlled cassette
# No credentials needed in pipeline
```

### 5. Document API Contracts

```python
# app/integrations/twilio/README.md
"""
Trust Hub API Contract:

POST /CustomerProfiles
- Creates customer profile for brand registration
- Request: FriendlyName, Type, Email
- Response: SID, FriendlyName, Type
- Time: Immediate
- Cost: $0

POST /Brands
- Submits brand for carrier approval
- Request: Type, CustomerProfileSid
- Response: SID, Status, DateCreated
- Time: 5-14 business days for approval
- Cost: $0 (first brand free, $15 per resubmission)
"""
```

---

## Troubleshooting

### "My cassette is too large"

Cassettes include full request/response bodies. If they're > 1MB:
- Remove sensitive data fields from responses
- Record only successful scenarios (failures are tested with mocks)
- Use separate cassettes for different features

### "VCR says 'interaction not found'"

```bash
# Ensure VCR_RECORD_MODE is set correctly
# 'once' = record if missing, replay if exists (development)
# 'all' = always record new (when updating API)
# 'none' = only replay (CI/CD)

export VCR_RECORD_MODE=all
pytest tests/sms/registration/test_vcr.py -v
```

### "Credentials are being recorded in cassette"

```python
# Filter sensitive data
twilio_vcr = vcr.VCR(
    filter_headers=["authorization"],
    filter_post_data_parameters=["AccountSid", "AuthToken"],
)
```

### "Should I commit cassettes to git?"

✅ **Yes, commit cassettes.** They are:
- Test fixtures (like JSON fixtures)
- Stable (don't change unless API changes)
- Not sensitive (credentials are filtered)
- Necessary for CI/CD (enables running tests without credentials)

---

## Related Guides

- **[Integration Patterns](integration-patterns.md)** - How to structure integration clients
- **[Testing Style Guide](TESTING_STYLE_GUIDE.md)** - Testing pyramid and E2E vs integration patterns
- **[Error Handling & Cleanup](error-handling.md)** - Compensation patterns for external APIs
- **[Decision Frameworks](decision-frameworks.md)** - Decision matrices for integration choices

---

## Summary

**The workflow for adding new third-party integrations:**

1. **Phase 1 (Development)**: Use mocks on frontend (MSW) and backend (@patch) for fast iteration → No credentials, instant feedback
2. **Phase 2 (Testing)**: Write E2E/integration tests with mocks → No API costs, comprehensive coverage
3. **Phase 3 (Validation)**: Record ONE VCR cassette with real API → Validates contract, $5-50 one-time cost
4. **Phase 4 (Production)**: Deploy with real credentials, VCR replays in CI/CD → Real APIs for customers, free tests

This follows industry best practices because:
- ✅ **Mocks enable fast development** (iterate in minutes, not hours)
- ✅ **Tests validate behavior without costs** (comprehensive coverage for free)
- ✅ **VCR validates once, replays forever** (cost-effective validation strategy)
- ✅ **CI/CD stays fast and free** (cassette replay, no external calls)
