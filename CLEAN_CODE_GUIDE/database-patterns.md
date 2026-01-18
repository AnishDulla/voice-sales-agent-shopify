# Database Patterns & Transaction Boundaries

This guide covers transaction management, commit/refresh patterns, and how to prevent common SQLAlchemy async errors when working with PostgreSQL and AsyncSession.

## Quick Navigation

- [Transaction Boundaries](#transaction-boundaries) - Where commits belong
- [Commit and Refresh Patterns](#commit-and-refresh-patterns) - Three core patterns
- [Helper Method Design](#helper-method-design) - When NOT to commit
- [Atomic Operations](#atomic-operations) - Race condition prevention
- [Async Pitfalls](#async-pitfalls) - Detached objects and greenlet errors
- [Testing Considerations](#testing-considerations) - flush() vs commit()
- [SQLAlchemy Relationship Patterns](#sqlalchemy-relationship-patterns) - Unidirectional vs bidirectional

## Transaction Boundaries

### The Golden Rule

**Commits belong at the service method boundary, not inside helper methods.**

```
┌─────────────────────────────────┐
│ Router Layer (FastAPI routes)   │  ← Never commits
├─────────────────────────────────┤
│ Service Layer (business logic)  │  ← COMMITS HERE at method boundary
├─────────────────────────────────┤
│ Helper Methods (pure transform) │  ← NEVER commits
├─────────────────────────────────┤
│ Integration Layer (external API)│  ← Never commits (see integration-patterns.md)
└─────────────────────────────────┘
```

### Layer Rules

| Layer | Can Commit? | Reason |
|-------|-----------|--------|
| Router | ❌ NO | Framework layer, delegates to services |
| Service | ✅ YES | Owns transaction boundaries and business logic |
| Helper (service private) | ❌ NO | Helpers should be pure transformations |
| Integration | ❌ NO | Should only call external APIs, return data |

### Why This Matters

When helpers commit:
1. ❌ Creates hidden side effects (caller doesn't expect mutations)
2. ❌ Breaks transaction atomicity (multiple commits = multiple transactions)
3. ❌ Causes detached object errors in async contexts
4. ❌ Makes code unpredictable for callers

## Commit and Refresh Patterns

### Pattern 1: Standard CRUD (Create/Update)

**Use this for:** Creating new entities or major updates

```python
# ✅ CORRECT: Commit at service method boundary

async def create_subscription(
    self, db: AsyncSession, org: Organization, request: SubscriptionRequest
) -> Subscription:
    """Create a new subscription for an organization"""

    # 1. Do all the work
    subscription = Subscription(
        id=str(uuid4()),
        organization_id=org.id,
        stripe_id=request.stripe_id,
        status="active",
    )
    db.add(subscription)

    # 2. Single commit at method boundary (not in helpers!)
    await db.commit()

    # 3. Refresh to reload DB-generated values (like created_at, updated_at)
    await db.refresh(subscription)

    # 4. Build response (helper, no commit)
    return await self._build_subscription_response(subscription)
```

**Why refresh()?** When `updated_at` has `onupdate=func.now()`, SQLAlchemy needs to reload the value from the database after commit.

### Pattern 2: Update-Only (In-Transaction Modifications)

**Use this for:** Updating existing entities within the same transaction

```python
# ✅ CORRECT: Use flush() instead of commit() for intermediate updates

async def update_organization_settings(
    self, db: AsyncSession, org: Organization, settings: UpdateRequest
) -> Organization:
    """Update organization settings in-place"""

    # 1. Modify object
    org.settings = settings.settings_dict
    org.max_users = settings.max_users

    # 2. Use flush() to persist immediately (same transaction)
    await db.flush()

    # 3. Can safely access attributes - object still attached
    print(org.id)  # ✅ Works
    print(org.updated_at)  # ✅ Works (doesn't lazy-load)

    # Caller will commit when ready
    return org
```

**Key difference:**
- `flush()`: Makes changes visible in current transaction, but doesn't commit
- `commit()`: Closes transaction, detaches objects

### Pattern 3: Atomic Upsert (Race-Condition Safe)

**Use this for:** Creating or updating when concurrent requests might create duplicates

```python
# ✅ CORRECT: PostgreSQL INSERT ON CONFLICT is atomic

async def upsert_contact_by_phone(
    self, db: AsyncSession, org: Organization, phone: str, data: dict
) -> Contact:
    """Create contact or update if already exists (race-condition safe)"""

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # 1. Use atomic INSERT ON CONFLICT
    stmt = (
        pg_insert(Contact)
        .values(
            id=str(uuid4()),
            organization_id=org.id,
            phone=phone,
            **data
        )
        .on_conflict_do_update(
            index_elements=["organization_id", "phone"],
            set_=data,
        )
        .returning(Contact)
    )

    result = await db.execute(stmt)
    contact = result.scalar_one()

    # 2. Flush (no commit needed - atomic operation already safe)
    await db.flush()

    return contact
```

**Why atomic upsert?**
- ❌ BAD: Manual SELECT-then-INSERT has race condition (concurrent requests both pass SELECT, both INSERT)
- ✅ GOOD: Database-level INSERT ON CONFLICT is atomic (only one succeeds)

**When to use each pattern:**

```python
# Pattern 1: New entity creation
async def create_subscription(...):
    subscription = Subscription(...)
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

# Pattern 2: Update in-place
async def update_settings(...):
    org.settings = new_settings
    await db.flush()  # No commit

# Pattern 3: Concurrent creation
async def ensure_contact_exists(...):
    result = await db.execute(
        pg_insert(Contact)
        .values(...)
        .on_conflict_do_update(...)
        .returning(Contact)
    )
    contact = result.scalar_one()
    await db.flush()
```

## Helper Method Design

### Rule: Helpers Never Commit

This is what caused the greenlet error in `PaymentService._build_subscription_response_with_pricing()`.

```python
# ❌ BAD: Helper method committing (causes greenlet errors!)

async def _build_subscription_response_with_pricing(
    self, subscription: Subscription
) -> SubscriptionResponse:
    """Build response with pricing"""

    # Fetch pricing from Stripe
    pricing = await self.stripe_client.get_upcoming_invoice(subscription.id)

    # Update subscription
    subscription.current_period_start = pricing["period_start"]
    subscription.current_period_end = pricing["period_end"]

    # ❌ WRONG: Helper method should not commit
    await self.db.commit()

    # ❌ Later, accessing attributes causes greenlet error
    # Because object is now detached from session
    return SubscriptionResponse(
        updated_at=subscription.updated_at,  # ← GREENLET ERROR!
    )
```

### The Right Way

```python
# ✅ GOOD: Service method controls commits, helpers are pure

async def get_subscription(self, org_id: str) -> SubscriptionResponse:
    """Get subscription for an organization (public method)"""

    subscription = await self.get_subscription_by_org_id(org_id)
    if subscription:
        # Helper does NOT commit - just transforms data
        return await self._build_subscription_response_with_pricing(subscription)
    return None

async def _build_subscription_response_with_pricing(
    self, subscription: Subscription
) -> SubscriptionResponse:
    """Build response with pricing (helper - no commits!)"""

    # Fetch pricing from Stripe
    pricing = await self.stripe_client.get_upcoming_invoice(subscription.id)

    # Update subscription object (but don't commit)
    subscription.current_period_start = pricing["period_start"]
    subscription.current_period_end = pricing["period_end"]

    # Build response (helper - let caller decide when to commit)
    return SubscriptionResponse(
        id=subscription.id,
        current_period_start=subscription.current_period_start,
        updated_at=subscription.updated_at,  # ✅ Safe: object still attached
    )

async def sync_subscription_from_stripe(
    self, org_id: str
) -> SubscriptionResponse:
    """Sync subscription from Stripe and persist (public method)"""

    subscription = await self.get_subscription_by_org_id(org_id)

    # Do the sync (includes updates)
    response = await self._build_subscription_response_with_pricing(subscription)

    # Service method controls the commit
    await self.db.commit()
    await self.db.refresh(subscription)

    return response
```

**Key insight:** `get_subscription` is a read-only GET endpoint that should never write. `sync_subscription_from_stripe` is the write operation that controls the transaction.

### Helper Method Checklist

- [ ] Does this method have a name that suggests side effects? (e.g., `_sync_`, `_update_`, `_create_`)
- [ ] Are you calling `await db.commit()` in this method?
- [ ] Are you accessing lazy-loaded attributes after commit?

If yes to any, move the commit to the caller.

## Atomic Operations

### INSERT ON CONFLICT DO UPDATE (Atomic Upsert)

**Problem:** Race conditions with concurrent requests

```python
# ❌ BAD: Race condition window between SELECT and INSERT

async def create_contact(self, org_id: str, phone: str):
    # Thread A: SELECT finds no contact with this phone
    existing = await db.execute(
        select(Contact).where(
            Contact.organization_id == org_id,
            Contact.phone == phone,
        )
    )
    contact = existing.scalar_one_or_none()

    # Thread B ALSO: SELECT finds no contact with this phone
    # Now both threads will try to INSERT...

    if not contact:
        # Thread A: INSERT succeeds
        contact = Contact(...)
        db.add(contact)
        await db.commit()  # ✅

    # Thread B: INSERT fails with IntegrityError!
    # (unique constraint violated)
    return contact
```

**Solution:** Use database-level atomic operation

```python
# ✅ GOOD: Atomic INSERT ON CONFLICT

async def create_contact(self, org_id: str, phone: str):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = (
        pg_insert(Contact)
        .values(
            id=str(uuid4()),
            organization_id=org_id,
            phone=phone,
            name="",
        )
        .on_conflict_do_update(
            index_elements=["organization_id", "phone"],
            set_={"updated_at": func.now()},
        )
        .returning(Contact)
    )

    result = await db.execute(stmt)
    contact = result.scalar_one()
    await db.flush()

    return contact
```

**Why this works:**
- Database handles the race condition at the transaction level
- Only one INSERT or UPDATE succeeds
- Atomicity guaranteed at the database layer
- No need for application-level locking

## Async Pitfalls

### Greenlet Error: Accessing Detached Objects

**Error:** `greenlet_spawn has not been called; can't call await_only() here`

```python
# ❌ BAD: Accessing attributes on detached object

async def get_subscription(self, org_id: str):
    subscription = await self.db.get(Subscription, org_id)

    # Commit detaches the object
    await self.db.commit()

    # Now accessing attributes tries to lazy-load from closed session
    return {
        "id": subscription.id,  # ✅ OK (primary key is cached)
        "updated_at": subscription.updated_at,  # ❌ GREENLET ERROR!
    }
```

**Cause:** After `commit()`, the SQLAlchemy session closes. Accessing lazy-loaded attributes (like `updated_at` with `onupdate=func.now()`) tries to fetch from the closed session in async context.

**Solution 1: Refresh after commit**

```python
# ✅ GOOD: Refresh to reload all attributes

async def get_subscription(self, org_id: str):
    subscription = await self.db.get(Subscription, org_id)

    # Make changes
    subscription.status = "active"

    await self.db.commit()
    await self.db.refresh(subscription)  # ← Re-attach and reload

    # Now safe to access any attribute
    return {
        "id": subscription.id,
        "updated_at": subscription.updated_at,  # ✅ OK
    }
```

**Solution 2: Eager load before commit**

```python
# ✅ ALSO GOOD: Pre-load attributes before commit

from sqlalchemy import joinedload

async def get_subscription(self, org_id: str):
    # Load subscription with all attributes eager-loaded
    stmt = select(Subscription).where(
        Subscription.organization_id == org_id
    ).options(
        joinedload(Subscription.organization),
    )

    result = await self.db.execute(stmt)
    subscription = result.scalar_one_or_none()

    # Commit
    await self.db.commit()

    # Attributes already loaded, no lazy-load needed
    return subscription
```

**Solution 3: Don't commit in the first place**

```python
# ✅ BEST: If it's a read operation, don't commit!

async def get_subscription(self, org_id: str):
    subscription = await self.db.get(Subscription, org_id)

    # No commit needed for read operation
    return {
        "id": subscription.id,
        "updated_at": subscription.updated_at,  # ✅ OK
    }
```

### MissingGreenlet Error

**Full error:** `greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place?`

This happens when SQLAlchemy tries to use synchronous IO (like a database ping) in an async context after the object is detached.

**Prevention:** Follow the patterns above - commit at service boundaries and refresh immediately.

## Testing Considerations

### Use `flush()` Instead of `commit()` in Tests

**Why?** Tests share a transaction that rolls back after each test. Committing breaks this isolation.

See [TESTING_STYLE_GUIDE.md](TESTING_STYLE_GUIDE.md) for detailed patterns.

```python
# ✅ GOOD: Test uses flush() for isolation

@pytest.fixture
async def test_subscription(db_transaction):
    """Create test subscription that can be rolled back"""
    org = OrganizationFactory.create()

    subscription = Subscription(
        organization_id=org.id,
        stripe_id="sub_test_123",
        status="active",
    )
    db_transaction.add(subscription)

    # Use flush, not commit!
    await db_transaction.flush()

    # Transaction rolls back after test
    return subscription
```

### Testing Commit Behavior

When testing actual commit behavior (e.g., atomic upsert):

```python
# ✅ GOOD: Use separate session for commit testing

async def test_concurrent_contact_creation(db_transaction):
    """Test atomic INSERT ON CONFLICT with concurrent sessions"""

    org = OrganizationFactory.create()
    await db_transaction.flush()

    # Create two separate sessions (simulates concurrent requests)
    async with async_sessionmaker() as session1, async_sessionmaker() as session2:
        # Both try to create same contact
        results = await asyncio.gather(
            create_contact(session1, org.id, "555-1234"),
            create_contact(session2, org.id, "555-1234"),
            return_exceptions=True,
        )

        # Only one should succeed (atomic upsert)
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 1
```

## Common Mistakes

| ❌ Mistake | ✅ Fix | Why |
|-----------|--------|-----|
| Helper methods commit | Move commit to caller | Transaction boundaries should be at service level |
| Accessing attributes after commit | Use refresh() | Attributes become lazy-loaded on detached objects |
| Manual SELECT-then-INSERT | Use atomic INSERT ON CONFLICT | Race condition between SELECT and INSERT |
| Multiple commits in operation | Single commit at method boundary | Breaks atomicity, multiple transactions |
| Committing in integration layer | Keep integration layer pure | Should only call external APIs |

## SQLAlchemy Relationship Patterns

### Unidirectional Relationships (Preferred)

**Prefer unidirectional relationships.** Query children through services, not ORM relationships.

```python
# Child references parent only - parent has NO relationship back
class OrganizationMember(Base):
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    organization: Mapped["Organization"] = relationship("Organization")

class Organization(Base):
    # No members relationship - use OrganizationService queries instead
    pass
```

**Benefits:**
- No circular imports or TYPE_CHECKING needed on parent
- Models stay thin - pure data containers
- All query logic lives in services (testable, explicit)
- Easier to reason about data flow

**Query children through services:**
```python
# OrganizationService
async def _get_member_count(self, organization_id: str) -> int:
    result = await self.db.execute(
        select(func.count(OrganizationMember.id))
        .where(OrganizationMember.organization_id == organization_id)
    )
    return result.scalar() or 0
```

### Child → Parent Relationships (Acceptable)

Unidirectional child-to-parent relationships are fine and often useful:

```python
class RingGroupMember(Base):
    ring_group_id: Mapped[str] = mapped_column(ForeignKey("ring_groups.id"))
    ring_group: Mapped["RingGroup"] = relationship("RingGroup")  # Useful for quick access
```

This requires TYPE_CHECKING for the parent import, which is acceptable for same-layer (Model → Model) imports.

### Bidirectional Relationships (Avoid)

Bidirectional relationships (`back_populates`) create coupling and often go unused:

```python
# ❌ AVOID: Parent knows about children
class Organization(Base):
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="organization"
    )
```

**Problems:**
- Requires TYPE_CHECKING imports on parent (circular dependency)
- Often unused - code queries through services anyway
- Couples parent model to all child models

**Only use if:** You have a compelling reason AND the relationship is actively used in code (not just "might be useful").

### TYPE_CHECKING for Model Imports

Using `TYPE_CHECKING` for child→parent imports is acceptable:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.organization import Organization

class OrganizationMember(Base):
    organization: Mapped["Organization"] = relationship("Organization")
```

**When TYPE_CHECKING IS a code smell:**
- Parent model importing children (use services instead)
- Model imports from Service layer → Fix architecture
- Service imports from Router layer → Fix architecture

---

## Summary

**The Three Patterns:**

```python
# 1. Standard CRUD
db.add(entity)
await db.commit()
await db.refresh(entity)

# 2. Update-only
entity.field = new_value
await db.flush()

# 3. Atomic upsert
result = await db.execute(pg_insert(...).on_conflict_do_update(...).returning(...))
entity = result.scalar_one()
await db.flush()
```

**The Golden Rule:**
- **Commits at service method boundaries** (public methods control transactions)
- **No commits in helpers** (pure transformations)
- **No commits in integration layer** (data-fetching only)

**The Greenlet Rule:**
- After `commit()`, call `refresh()` if accessing lazy-loaded attributes
- Or use atomic operations that don't require commit
- Or don't commit for read-only operations

---

## References

- [Service Architecture](service-architecture.md) - Service layer patterns and guidelines
- [Integration Patterns](integration-patterns.md) - External API and layer separation
- [Testing Style Guide](TESTING_STYLE_GUIDE.md) - flush() vs commit() in tests
- SQLAlchemy Async docs: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
