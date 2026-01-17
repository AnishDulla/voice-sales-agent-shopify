# Frontend E2E Testing Guide (Playwright)

Best practices and patterns for writing end-to-end tests for the web portal using Playwright. These patterns were developed and validated while building the contact filter persistence feature.

_IMPORTANT_: Test user behavior through the UI, not implementation details. Tests should validate what users see and do, not how the code works internally.

## TL;DR - Quick Reference

**Testing Distribution:** 70% E2E through UI, 20% Integration (component + mocks), 10% Unit (pure functions)

| Pattern | How to Use | When to Use |
|---------|------------|-------------|
| **Helper Classes** | `await filterHelpers.applyFilter(options)` | Complex multi-step UI flows |
| **API Data Factories** | `await createContacts(page, data, email)` | Fast test data setup |
| **`data-testid` Selectors** | `page.locator('[data-testid="filter-button"]')` | All stable UI selectors |
| **Modal Scoping** | `modal.locator('select').first()` | Avoiding wrong element selection |
| **Auto-Retry Assertions** | `await expect(chip).toBeVisible({ timeout: 10000 })` | Async UI state validation |

**Key Principle:** Set up test data via API (fast), validate behavior through UI (tests user experience).

---

## 🧪 Testing Philosophy for Frontend E2E

**E2E Tests Validate Real User Journeys**

Frontend E2E tests should simulate actual user behavior through the browser:

```
Traditional Unit Tests          Frontend E2E Tests
      Mocks (90%)                  Real UI (70%)
   Fast feedback                Real user journeys
Low confidence in UX          High confidence in UX
```

### Why E2E-First for Frontend?

- ✅ **Integration is where UI bugs hide**: Components work individually but fail when composed
- ✅ **Validates real user experience**: Tests what users actually see and click
- ✅ **Catches async timing issues**: React Query, animations, modal timing, etc.
- ✅ **Tests accessibility**: Real browser interactions validate keyboard nav, screen readers
- ✅ **Resilient to refactoring**: Tests behavior (what users do), not implementation (how components work)

### Testing Strategy: 70% E2E UI, 20% Integration, 10% Unit

**E2E Tests (70%)**: Critical user workflows through browser
- User authentication and navigation
- Form submissions and validations
- Filters, sorting, pagination
- Modal interactions and dropdowns
- Data persistence after page reload

**Integration Tests (20%)**: Component + API mocking
- React Query hooks with MSW
- Complex component state logic
- Error boundary handling

**Unit Tests (10%)**: Pure utility functions
- Date formatters, validators
- Business rule calculations
- Data transformations

---

## 📋 Test Selector Strategies

### Rule 1: Use `data-testid` for Stable Selectors

Always prefer `data-testid` attributes over text-based or CSS class selectors.

**Good - Stable test selectors:**
```typescript
// Component
<button data-testid="filter-button-container">Filter</button>
<div data-testid="filter-chip-0">Status is interested</div>

// Test
await page.click('[data-testid="filter-button-container"]');
await expect(page.locator('[data-testid="filter-chip-0"]')).toBeVisible();
```

**Bad - Brittle selectors:**
```typescript
// ❌ Text-based - breaks when copy changes
await page.click('button:has-text("Filter")');

// ❌ CSS class - breaks when styling refactors
await page.locator('.flex.items-center button').first();

// ❌ Generic role - ambiguous when multiple buttons exist
await page.getByRole('button', { name: /filter/i });
```

### Rule 2: Use Prefix Patterns for Dynamic Lists

When rendering dynamic lists, use `data-testid` with numeric suffixes:

```typescript
// Component
{filters.map((filter, index) => (
  <div key={filter.id} data-testid={`filter-chip-${index}`}>
    <span>{filter.field} {filter.operator} {filter.value}</span>
    <button data-testid={`remove-filter-${index}`}>×</button>
  </div>
))}

// Test
await expect(page.locator('[data-testid="filter-chip-0"]')).toContainText('status');
await page.click('[data-testid="remove-filter-0"]');

// Select all filter chips
const chips = page.locator('[data-testid^="filter-chip-"]');
await expect(chips).toHaveCount(3);
```

### Rule 3: Scope Selectors to Containers

When interacting with modals, dropdowns, or portals, always scope selectors to the container to avoid selecting wrong elements.

**Good - Scoped to modal:**
```typescript
// Find the specific modal container
const modal = page.locator('.fixed.inset-0.z-50').filter({ hasText: 'Filter by' });
await expect(modal).toBeVisible({ timeout: 5000 });

// All selectors scoped to this modal
const operatorSelect = modal.locator('select').first();
const valueInput = modal.locator('input[type="text"]').first();
const applyButton = modal.locator('button:has-text("Apply Filter")');

await operatorSelect.selectOption('is');
await valueInput.fill('interested');
await applyButton.click();
```

**Bad - Global selectors:**
```typescript
// ❌ Could select dropdown from WRONG modal if multiple modals exist
const operatorSelect = page.locator('select').first();

// ❌ Could click Apply button from wrong modal
const applyButton = page.locator('button:has-text("Apply")').first();
```

**Why scoping matters:**
- React portals render modals outside component hierarchy
- Multiple modals can exist in DOM simultaneously (React 18 transitions)
- Global selectors are ambiguous when UI has duplicate elements

### Real-World Example: Modal Scoping

From `playwright/helpers/contactFilters.ts`:

```typescript
async applyFilter(options: {
  columnName: string;
  operator: 'is' | 'is not' | 'contains';
  value: string;
}): Promise<void> {
  // Step 1: Click filter button
  await this.page.click('[data-testid="filter-button-container"] button');

  // Step 2: Wait for filter dropdown
  const filterSearchInput = this.page.locator('input[placeholder*="Search attributes"]');
  await expect(filterSearchInput).toBeVisible({ timeout: 5000 });

  // Step 3: Search and select column
  await filterSearchInput.fill(options.columnName);
  await this.page.locator('[role="menuitem"]')
    .filter({ hasText: options.columnName })
    .first()
    .click();

  // Step 4: Scope all interactions to the modal
  const modal = this.page.locator('.fixed.inset-0.z-50')
    .filter({ hasText: 'Filter by' });
  await expect(modal).toBeVisible({ timeout: 5000 });

  // Step 5: All selectors scoped to modal (prevents wrong element selection)
  const operatorSelect = modal.locator('select').first();
  await operatorSelect.selectOption(options.operator);

  const valueInput = modal.locator('input[type="text"]').first();
  await valueInput.fill(options.value);

  const applyButton = modal.locator('button:has-text("Apply Filter")');
  await applyButton.click();
}
```

---

## 🔧 Helper Class Pattern for Complex UI Flows

### Rule: Encapsulate Multi-Step UI Interactions in Helper Classes

Complex UI flows (modals, dropdowns, multi-step forms) should be extracted into reusable helper classes. This keeps tests focused on business logic, not UI mechanics.

**Benefits:**
- Tests stay readable and focused on user journeys
- UI changes only require updating helpers, not all tests
- Helpers become living documentation of UI interaction patterns
- Easier to maintain when components refactor

### Helper Class Structure

```typescript
// playwright/helpers/featureHelpers.ts
import { Page, expect } from '@playwright/test';

export class FeatureHelpers {
  constructor(private page: Page) {}

  /**
   * Public methods for test use - each represents a user action
   */
  async performComplexAction(options: {...}): Promise<void> {
    // Multi-step UI interaction logic
  }

  async verifyExpectedState(expected: {...}): Promise<void> {
    // Assertion helpers with waits and retries
  }

  /**
   * Private helper methods for internal use
   */
  private async waitForModalToOpen(): Promise<Locator> {
    // Reusable internal logic
  }
}
```

### Real-World Example: ContactFilterHelpers

From `clients/web_portal/playwright/helpers/contactFilters.ts`:

```typescript
export class ContactFilterHelpers {
  constructor(private page: Page) {}

  /**
   * Apply a filter using the UI:
   * 1. Click "Filter" button
   * 2. Search for and select column
   * 3. Select condition operator
   * 4. Enter value
   * 5. Click "Apply Filter"
   */
  async applyFilter(options: {
    columnName: string;
    operator: 'is' | 'is not' | 'contains' | 'equals' | 'gte' | 'lte';
    value: string;
  }): Promise<void> {
    // ... 50 lines of UI interaction logic ...
  }

  /**
   * Save current filters to the currently selected segment
   */
  async saveFiltersToCurrentSegment(): Promise<void> {
    const saveButton = this.page.locator('[data-testid="save-to-segment-button"]');
    await expect(saveButton).toBeVisible({ timeout: 5000 });
    await saveButton.click();
    await expect(saveButton).not.toBeVisible({ timeout: 5000 });
    await this.page.waitForTimeout(500); // API call completion
  }

  /**
   * Select a segment from the dropdown menu
   */
  async selectSegmentFromDropdown(segmentName: string): Promise<void> {
    const segmentTrigger = this.page.locator('[data-testid="segment-dropdown-trigger"]');
    await expect(segmentTrigger).toBeVisible({ timeout: 10000 });
    await segmentTrigger.click();
    await this.page.waitForTimeout(500); // Dropdown animation

    const segmentMenuItem = this.page.locator('[role="menuitem"]')
      .filter({ hasText: segmentName })
      .first();
    await expect(segmentMenuItem).toBeVisible({ timeout: 10000 });
    await segmentMenuItem.click({ force: true }); // Bypass animation intercepts
    await this.page.waitForTimeout(1000); // Selection completion
  }

  /**
   * Verify a filter chip is displayed with expected values
   */
  async expectFilterChip(index: number, expected: {
    field: string;
    operator: string;
    value: string;
  }): Promise<void> {
    const chip = this.page.locator(`[data-testid="filter-chip-${index}"]`);
    await expect(chip).toBeVisible({ timeout: 10000 });
    await expect(chip).toContainText(expected.field, { ignoreCase: true });
    await expect(chip).toContainText(expected.operator, { ignoreCase: true });
    await expect(chip).toContainText(expected.value, { ignoreCase: true });
  }

  /**
   * Verify contacts count matches expected value
   * Waits for React Query to fetch data (up to 10 seconds)
   */
  async expectContactsCount(expected: number): Promise<void> {
    await expect(this.page.locator('[data-testid="contacts-count-display"]')).toContainText(
      `of ${expected} contact`,
      { timeout: 10000 }
    );
  }
}
```

**Usage in tests:**

```typescript
test('Filters persist when user reloads the page', async ({ page }) => {
  const filterHelpers = new ContactFilterHelpers(page);

  // Clean test code - focuses on user journey, not UI mechanics
  await filterHelpers.applyFilter({
    columnName: 'Status',
    operator: 'is',
    value: 'interested',
  });

  await filterHelpers.saveFiltersToCurrentSegment();
  await filterHelpers.expectContactsCount(3);

  await page.reload(); // User journey: page reload

  await filterHelpers.expectFilterChip(0, {
    field: 'status',
    operator: 'is',
    value: 'interested',
  });
  await filterHelpers.expectContactsCount(3);
});
```

**Without helpers (BAD):**

```typescript
test('Filters persist when user reloads the page', async ({ page }) => {
  // ❌ Verbose, hard to read, duplicated across tests
  await page.click('[data-testid="filter-button-container"] button');
  await page.waitForTimeout(300);
  const filterSearchInput = page.locator('input[placeholder*="Search attributes"]');
  await expect(filterSearchInput).toBeVisible({ timeout: 5000 });
  await filterSearchInput.fill('Status');
  await page.waitForTimeout(200);
  const columnOption = page.locator('[role="menuitem"]').filter({ hasText: 'Status' }).first();
  await expect(columnOption).toBeVisible({ timeout: 5000 });
  await columnOption.click();
  await page.waitForTimeout(500);
  // ... 40 more lines of UI mechanics ...

  await page.reload();

  // ❌ More verbose assertion logic
  const chip = page.locator('[data-testid="filter-chip-0"]');
  await expect(chip).toBeVisible({ timeout: 10000 });
  await expect(chip).toContainText('status', { ignoreCase: true });
  // ... etc
});
```

---

## 🏭 API Data Factory Pattern

### Rule: Set Up Test Data via API, Validate Behavior via UI

**Setup via API (fast, reliable):**
- Create test users, organizations, contacts, etc.
- 10x faster than creating data through UI
- More reliable (no flaky UI interactions)
- Enables realistic test scenarios with bulk data

**Validate via UI (tests user experience):**
- Apply filters, sort, paginate through browser
- Submit forms, click buttons
- Verify UI displays correct data
- Test edge cases and error states

### Test Infrastructure Endpoints

Backend provides special endpoints for E2E test data setup. These bypass normal authentication in favor of header-based auth.

**Backend Pattern:**

```python
# app/test_infrastructure/router.py
@router.post("/contacts/bulk", response_model=BulkCreateContactResponse)
async def bulk_create_test_contacts(
    request: BulkCreateContactRequest,
    db: DatabaseDep,
    _: None = Depends(verify_test_access),  # X-Test-Secret header auth
):
    """
    Create multiple contacts for E2E testing.
    Uses user_email to identify which organization owns the data.
    """
    # Look up user by email to get organization
    result = await db.execute(
        select(User).where(User.email == request.user_email)
    )
    user = result.scalar_one_or_none()
    if not user or not user.organizationId:
        raise HTTPException(status_code=404, detail="User not found")

    # Create contacts via service
    service = TestInfrastructureService(db)
    return await service.bulk_create_test_contacts(
        organization_id=user.organizationId,
        contacts_data=request.contacts,
    )
```

**Key Design Decisions:**
- `user_email` parameter identifies which organization owns the data
- `X-Test-Secret` header bypasses Firebase auth (enables `page.request()` calls)
- Service layer handles actual creation logic
- Returns created entities with IDs for test assertions

### Frontend Data Factory Helpers

```typescript
// playwright/lib/datafactory/contacts.ts
import { Page } from '@playwright/test';
import type { CreateContactsResponse } from './types';

const API_URL = 'http://localhost:8001'; // Backend test server

function getTestInfraHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    'X-Test-Secret': 'test-token-seeder', // Special auth for test endpoints
  };
}

export async function createContacts(
  page: Page,
  contacts: Array<{
    name: string;
    email: string;
    phoneNumber?: string;
    status?: 'new' | 'interested' | 'qualified' | 'lost';
    source?: 'manual' | 'import' | 'api';
  }>,
  userEmail: string
): Promise<CreateContactsResponse> {
  const response = await page.request.post(
    `${API_URL}/api/v1/test-infrastructure/contacts/bulk`,
    {
      headers: getTestInfraHeaders(),
      data: {
        user_email: userEmail,
        contacts: contacts,
      },
    }
  );

  if (!response.ok()) {
    throw new Error(`Failed to create contacts: ${response.status()} ${await response.text()}`);
  }

  return response.json();
}

export async function createSegment(
  page: Page,
  segment: {
    name: string;
    description?: string;
    filters?: {
      conditions: Array<{
        field: string;
        operator: string;
        value: string;
      }>;
    };
  },
  userEmail: string
): Promise<{ id: string; name: string }> {
  const response = await page.request.post(
    `${API_URL}/api/v1/test-infrastructure/segments`,
    {
      headers: getTestInfraHeaders(),
      data: {
        user_email: userEmail,
        ...segment,
      },
    }
  );

  if (!response.ok()) {
    throw new Error(`Failed to create segment: ${response.status()} ${await response.text()}`);
  }

  return response.json();
}
```

### Real-World Example: Test Using API Data Factories

From `playwright/contacts/filter-persistence.e2e.ts`:

```typescript
test('Filters persist when user reloads the page', async ({ page }) => {
  // Setup: Create test data via API (FAST - 100ms)
  await createContacts(
    page,
    [
      { name: 'Interested Contact', email: 'interested@test.com', status: 'interested' },
      { name: 'Qualified Contact', email: 'qualified@test.com', status: 'qualified' },
      { name: 'New Contact', email: 'new@test.com', status: 'new' },
    ],
    user.email
  );

  // Navigate to page
  await page.goto('/dashboard/contacts');
  await page.waitForSelector('[data-testid="contacts-table-container"]');

  // Test: Apply filter through UI (validates UX)
  const filterHelpers = new ContactFilterHelpers(page);
  await filterHelpers.applyFilter({
    columnName: 'Status',
    operator: 'is',
    value: 'interested',
  });

  // Verify: UI shows correct filtered results
  await filterHelpers.expectContactsCount(1); // Only 1 interested contact
  await filterHelpers.expectFilterChip(0, {
    field: 'status',
    operator: 'is',
    value: 'interested',
  });

  // Save and reload (critical user journey)
  await filterHelpers.saveFiltersToCurrentSegment();
  await page.reload();

  // Assert: Filters persist after reload
  await filterHelpers.expectFilterChip(0, {
    field: 'status',
    operator: 'is',
    value: 'interested',
  });
  await filterHelpers.expectContactsCount(1);
});
```

**Benefits:**
- Setup takes 100ms via API vs 5+ seconds via UI
- Test data creation is reliable (no flaky UI clicks)
- Test focuses on critical user journey (apply filter → save → reload)
- Easy to create complex scenarios with bulk data

---

## ⏱️ Async UI State Handling

### Rule: Use Playwright Auto-Retry Assertions, Not Fixed Waits

Playwright automatically retries assertions until timeout. This is faster and more reliable than fixed waits.

**Good - Auto-retry assertions:**
```typescript
// Waits up to 10 seconds, but returns immediately when visible
await expect(modal).toBeVisible({ timeout: 10000 });

// Waits for React Query to fetch data and update count
await expect(page.locator('[data-testid="contacts-count"]')).toContainText(
  'of 47 contacts',
  { timeout: 10000 }
);
```

**Acceptable - Brief waits for animations:**
```typescript
// Brief wait for dropdown animation to complete
await page.waitForTimeout(300);

// Brief wait for modal transition
await page.waitForTimeout(500);
```

**Bad - Long fixed waits:**
```typescript
// ❌ Slows tests even when UI is fast
await page.waitForTimeout(5000);

// ❌ Prone to flakiness - might not be enough time
await page.waitForTimeout(2000);
await expect(modal).toBeVisible(); // Might still fail
```

### Handling React Query Data Fetching

When testing components that use React Query, assertions should wait for data to load:

```typescript
/**
 * Verify contacts count matches expected value.
 * Waits for React Query to fetch data (up to 10 seconds).
 */
async expectContactsCount(expected: number): Promise<void> {
  // Auto-retries until text appears or timeout
  await expect(
    this.page.locator('[data-testid="contacts-count-display"]')
  ).toContainText(
    `of ${expected} contact`,
    { timeout: 10000 } // Waits for React Query fetch + render
  );
}
```

### Handling Radix UI Animations

When interacting with Radix UI components (dropdowns, modals), brief waits ensure animations complete:

```typescript
async selectSegmentFromDropdown(segmentName: string): Promise<void> {
  // Click trigger
  const segmentTrigger = this.page.locator('[data-testid="segment-dropdown-trigger"]');
  await segmentTrigger.click();

  // Wait for dropdown animation (Radix UI transition)
  await this.page.waitForTimeout(500);

  // Click menu item (use force to bypass animation intercepts)
  const segmentMenuItem = this.page.locator('[role="menuitem"]')
    .filter({ hasText: segmentName })
    .first();
  await segmentMenuItem.click({ force: true });

  // Wait for selection to complete
  await this.page.waitForTimeout(1000);
}
```

### Cache Invalidation and Auto-Selection

When test infrastructure creates data via API, the frontend React Query cache may not know about it. Force a cache refresh:

```typescript
/**
 * Force segment list refresh by navigating away and back.
 * This triggers React Query to refetch segments.
 */
const forceSegmentListRefresh = async (page: Page) => {
  await page.goto('/dashboard'); // Navigate away
  await page.waitForTimeout(500);
  await page.goto('/dashboard/contacts'); // Navigate back (triggers refetch)
  await page.waitForSelector('[data-testid="contacts-table-container"]', {
    timeout: 10000,
  });
};

// Usage
await createSegment(page, segmentData, user.email); // API creates segment
await forceSegmentListRefresh(page); // Force cache to pick up new segment
```

---

## 🔄 Dynamic Field Type Handling

### Rule: Detect Field Types at Runtime, Don't Hardcode Assumptions

UI components render different controls based on field metadata (enum vs text, single vs multi-select). Tests should adapt to these differences.

**Dynamic Field Detection:**

```typescript
async applyFilter(options: {
  columnName: string;
  operator: 'is' | 'is not' | 'contains';
  value: string;
}): Promise<void> {
  // ... open modal and select column ...

  const modal = this.page.locator('.fixed.inset-0.z-50').filter({ hasText: 'Filter by' });

  // Select operator
  const operatorSelect = modal.locator('select').first();
  await operatorSelect.selectOption(options.operator);

  // Dynamically detect field type
  const selectCount = await modal.locator('select').count();

  if (selectCount > 1) {
    // Enum field (status, source) - uses select dropdown
    const valueSelect = modal.locator('select').last();
    await valueSelect.selectOption(options.value);
  } else {
    // Text/number field - uses input
    const valueInput = modal.locator('input[type="text"], input[type="number"]').first();
    await expect(valueInput).toBeVisible({ timeout: 5000 });
    await valueInput.fill(options.value);
  }

  // Click Apply
  await modal.locator('button:has-text("Apply Filter")').click();
}
```

**Why this pattern:**
- Field types can change (text → enum, single → multi)
- New fields may be added with different types
- Tests stay maintainable when schema evolves
- No need to hardcode field type knowledge in tests

---

## 🧩 Testing Patterns Checklist

Before writing a new E2E test, ask:

- [ ] **Helper class exists?** If complex UI flow, create/update helper class
- [ ] **Test data via API?** Use data factories for setup, not UI
- [ ] **`data-testid` selectors?** Ensure components have test IDs
- [ ] **Modal scoping?** Scope selectors to containers to avoid wrong elements
- [ ] **Auto-retry assertions?** Use Playwright timeouts, not fixed waits
- [ ] **Dynamic field handling?** Don't hardcode assumptions about field types
- [ ] **Cache invalidation?** Force refresh after API data creation
- [ ] **Real user journey?** Test validates what users actually do

---

## 📚 Reference Examples

### Complete E2E Test Example

From `playwright/contacts/filter-persistence.e2e.ts`:

```typescript
import { test, expect } from '@playwright/test';
import { ContactFilterHelpers } from '../helpers/contactFilters';
import { createContacts, createSegment } from '../lib/datafactory';
import { testLogin } from '../helpers/auth';

test.describe('Contact Filter Persistence E2E', () => {
  test('Segment switching properly resets filters', async ({ page }) => {
    // Setup: Login and create test user
    const user = await testLogin(page, {
      email: `test-${Date.now()}@example.com`,
      password: 'TestPassword123!',
    });

    // Setup: Create test contacts via API (FAST)
    await createContacts(
      page,
      [
        { name: 'Interested Contact', email: 'interested@test.com', status: 'interested' },
        { name: 'Qualified Contact', email: 'qualified@test.com', status: 'qualified' },
        { name: 'New Contact', email: 'new@test.com', status: 'new' },
      ],
      user.email
    );

    await page.goto('/dashboard/contacts');
    const filterHelpers = new ContactFilterHelpers(page);

    // Test: Create first segment with "interested" filter
    const segment1Name = `Interested Only ${Date.now()}`;
    await filterHelpers.createSegmentThroughUI({ name: segment1Name });

    await filterHelpers.applyFilter({
      columnName: 'Status',
      operator: 'is',
      value: 'interested',
    });

    await filterHelpers.expectFilterChip(0, {
      field: 'status',
      operator: 'is',
      value: 'interested',
    });

    await filterHelpers.saveFiltersToCurrentSegment();

    // Test: Create second segment with "qualified" filter
    const segment2Name = `Qualified Only ${Date.now()}`;
    await filterHelpers.createSegmentThroughUI({ name: segment2Name });

    await filterHelpers.applyFilter({
      columnName: 'Status',
      operator: 'is',
      value: 'qualified',
    });

    await filterHelpers.saveFiltersToCurrentSegment();

    // Assert: Switch back to segment1, filters should load correctly
    await filterHelpers.selectSegmentFromDropdown(segment1Name);

    await filterHelpers.expectFilterChip(0, {
      field: 'status',
      operator: 'is',
      value: 'interested',
    });

    await filterHelpers.expectContactsCount(1); // Only 1 interested contact
  });
});
```

---

## 🚨 Common Pitfalls and Solutions

### Pitfall 1: Flaky Tests Due to Wrong Element Selection

**Problem:** Global selector picks wrong dropdown when multiple exist.

```typescript
// ❌ Could select wrong dropdown
await page.locator('select').first().selectOption('interested');
```

**Solution:** Scope selectors to specific container.

```typescript
// ✅ Scoped to modal
const modal = page.locator('.fixed.inset-0.z-50').filter({ hasText: 'Filter by' });
await modal.locator('select').first().selectOption('interested');
```

### Pitfall 2: Tests Fail When Text Changes

**Problem:** Text-based selectors break when copy updates.

```typescript
// ❌ Breaks when button text changes
await page.click('button:has-text("Apply Filter")');
```

**Solution:** Use `data-testid` attributes.

```typescript
// ✅ Stable selector
await page.click('[data-testid="apply-filter-button"]');
```

### Pitfall 3: Race Conditions with React Query

**Problem:** Test assertions run before data loads.

```typescript
// ❌ Might assert before React Query finishes
await page.goto('/dashboard/contacts');
const count = await page.locator('[data-testid="contacts-count"]').textContent();
expect(count).toBe('3 contacts'); // Might still show loading state
```

**Solution:** Use auto-retry assertions with timeout.

```typescript
// ✅ Waits for React Query to load data
await expect(page.locator('[data-testid="contacts-count"]')).toContainText(
  '3 contacts',
  { timeout: 10000 }
);
```

### Pitfall 4: Slow Tests from UI-Based Setup

**Problem:** Creating test data through UI is slow and flaky.

```typescript
// ❌ 10+ seconds to create 5 contacts via UI
for (const contact of contacts) {
  await page.click('[data-testid="add-contact-button"]');
  await page.fill('[data-testid="contact-name"]', contact.name);
  await page.fill('[data-testid="contact-email"]', contact.email);
  await page.click('[data-testid="save-contact-button"]');
  await page.waitForTimeout(2000); // Wait for save
}
```

**Solution:** Use API data factories.

```typescript
// ✅ 100ms to create 5 contacts via API
await createContacts(page, contacts, user.email);
```

### Pitfall 5: Hardcoded Field Type Assumptions

**Problem:** Test assumes field is always text input, breaks when it becomes enum.

```typescript
// ❌ Assumes status is text input
await modal.locator('input').fill('interested'); // Breaks when status becomes enum dropdown
```

**Solution:** Dynamically detect field type.

```typescript
// ✅ Adapts to field type
const selectCount = await modal.locator('select').count();
if (selectCount > 1) {
  await modal.locator('select').last().selectOption('interested');
} else {
  await modal.locator('input').fill('interested');
}
```

---

## 📖 Further Reading

- **Playwright Official Docs**: https://playwright.dev/docs/writing-tests
- **React Query Testing**: https://tanstack.com/query/latest/docs/framework/react/guides/testing
- **Testing Library Principles**: https://testing-library.com/docs/guiding-principles/
- **Backend Testing Guide**: [TESTING_STYLE_GUIDE.md](./TESTING_STYLE_GUIDE.md)

---

_Last Updated: 2025-01-06 - Based on contact filter persistence E2E test development_
