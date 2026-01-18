# Feature Flags

Stello uses a custom feature flag system to gate features per-organization. By default, all flags are **OFF** (false) - features must be explicitly enabled.

## Quick Reference

### Frontend (Primary Use Case)

```typescript
import { useFeatureFlag } from '@/hooks/useFeatureFlag';

// In your component
const showCalendar = useFeatureFlag('personal_calendar');

if (showCalendar) {
  // render feature
}
```

### Enabling a Flag (Admin API)

```bash
# Enable for a specific organization
curl -X POST "$API_URL/api/v1/admin/feature-flags" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "personal_calendar", "organization_id": "org_abc123", "enabled": true}'

# Enable globally (all organizations)
curl -X POST "$API_URL/api/v1/admin/feature-flags" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "personal_calendar", "organization_id": null, "enabled": true}'
```

---

## Architecture

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     feature_flags table                      │
│  id | name              | organization_id | enabled          │
│  ---+-----------------+----------------+--------            │
│  1  | personal_calendar | org_abc        | true   (org-specific) │
│  2  | personal_calendar | NULL           | false  (global)       │
│  3  | new_dashboard     | NULL           | true   (global)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              GET /api/v1/feature-flags
              Returns: { "personal_calendar": true, "new_dashboard": true }
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Frontend (React Query Cache)                    │
│  useFeatureFlag('personal_calendar') → true                  │
│  useFeatureFlag('new_dashboard') → true                      │
│  useFeatureFlag('unknown_flag') → false (default)            │
└─────────────────────────────────────────────────────────────┘
```

### Resolution Order

1. **Org-specific flag** - If exists, use its value
2. **Global flag** (org_id = NULL) - Fallback if no org-specific flag
3. **Default** - `false` if no flag exists

---

## Naming Conventions

Use `snake_case` for flag names:

```
✅ Good: personal_calendar, new_dashboard, team_round_robin
❌ Bad:  personalCalendar, NewDashboard, TEAM_ROUND_ROBIN
```

---

## Frontend Usage

### Basic Check

```typescript
import { useFeatureFlag } from '@/hooks/useFeatureFlag';

function MyComponent() {
  const showFeature = useFeatureFlag('my_feature');

  if (!showFeature) return null;
  return <FeatureComponent />;
}
```

### With Loading State

```typescript
import { useFeatureFlagWithLoading } from '@/hooks/useFeatureFlag';

function MyComponent() {
  const { enabled, isLoading } = useFeatureFlagWithLoading('my_feature');

  if (isLoading) return <Spinner />;
  if (!enabled) return null;
  return <FeatureComponent />;
}
```

### Conditional Navigation Items

```typescript
const menuItems = [
  { label: 'Dashboard', path: '/dashboard' },
  // Only show if flag enabled
  ...(useFeatureFlag('new_reports')
    ? [{ label: 'Reports', path: '/reports' }]
    : []),
];
```

### Caching Behavior

- Flags are fetched **once** when the app loads
- Cached for **5 minutes** (staleTime)
- All `useFeatureFlag()` calls read from the same cache (no additional requests)

---

## Backend Usage (Future Expansion)

Currently, feature flags are **frontend-only**. The backend service exists but is primarily used for the API endpoint.

### When to Add Backend Flag Checks

- Gating new API endpoints
- A/B testing algorithms
- Rolling out new integrations
- Database migration toggles

### Option 1: Simple Check (1 DB query per check)

```python
from app.features.feature_flags.service import FeatureFlagService

@router.get("/my-endpoint")
async def my_endpoint(
    org_context: OrganizationContextDep,
    db: DatabaseDep,
):
    flag_service = FeatureFlagService(db)

    if not await flag_service.is_enabled("my_feature", org_context.organization_id):
        raise HTTPException(403, "Feature not enabled")

    # feature logic...
```

### Option 2: Add to OrganizationContext (Recommended for Multiple Checks)

If you need to check multiple flags per request, add flags to `OrganizationContext` to avoid multiple DB queries:

1. **Modify** `app/core/organization_context.py`:

```python
@dataclass
class OrganizationContext:
    organization_id: str
    role: str
    user_id: str
    feature_flags: dict[str, bool]  # ADD THIS
```

2. **Update** `get_organization_context_factory()` to load flags:

```python
async def get_organization_context(...):
    # ... existing code ...

    # Load feature flags (one query per request)
    flag_service = FeatureFlagService(db)
    feature_flags = await flag_service.get_all_flags(organization_id)

    return OrganizationContext(
        organization_id=organization_id,
        role=role,
        user_id=user_id,
        feature_flags=feature_flags,  # ADD THIS
    )
```

3. **Use** in any endpoint:

```python
@router.get("/my-endpoint")
async def my_endpoint(org_context: OrganizationContextDep):
    if not org_context.feature_flags.get("my_feature"):
        raise HTTPException(403, "Feature not enabled")
    # ...
```

### Option 3: Decorator Pattern

Create a decorator for gating entire endpoints:

```python
def require_feature_flag(flag_name: str):
    async def dependency(
        org_context: OrganizationContextDep,
        db: DatabaseDep,
    ):
        flag_service = FeatureFlagService(db)
        if not await flag_service.is_enabled(flag_name, org_context.organization_id):
            raise HTTPException(403, f"Feature '{flag_name}' not enabled")
    return Depends(dependency)

# Usage
@router.get("/calendar/settings", dependencies=[require_feature_flag("personal_calendar")])
async def get_calendar_settings(...):
    # ...
```

---

## Admin Operations

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/feature-flags` | GET | User token | Get all flags for current org |
| `/api/v1/feature-flags/{name}` | GET | User token | Check specific flag |
| `/api/v1/admin/feature-flags` | POST | Admin API key | Set a flag |
| `/api/v1/admin/feature-flags` | DELETE | Admin API key | Delete a flag |

### Setting Flags via API

```bash
# Set org-specific flag
curl -X POST "$API_URL/api/v1/admin/feature-flags" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "personal_calendar",
    "organization_id": "org_abc123",
    "enabled": true
  }'

# Set global flag (applies to all orgs without org-specific override)
curl -X POST "$API_URL/api/v1/admin/feature-flags" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "personal_calendar",
    "organization_id": null,
    "enabled": true
  }'
```

### Deleting Flags

```bash
curl -X DELETE "$API_URL/api/v1/admin/feature-flags" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "personal_calendar",
    "organization_id": "org_abc123"
  }'
```

---

## Database Schema

```sql
CREATE TABLE feature_flags (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    organization_id VARCHAR REFERENCES organizations(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(name, organization_id)
);
```

---

## Current Feature Flags

| Flag Name | Description | Status |
|-----------|-------------|--------|
| `personal_calendar` | Personal calendar settings page in sidebar | In development |

---

## Best Practices

1. **Default to OFF** - New features should be hidden until explicitly enabled
2. **Remove old flags** - After 100% rollout, remove the flag and conditional code
3. **Document flags** - Add new flags to the table above
4. **Use descriptive names** - `team_round_robin_booking` not `trr` or `feature_1`
5. **Keep frontend-only for now** - Add backend checks only when needed
