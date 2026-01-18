# Frontend Architecture Guide for Stello AI

This guide documents clean code principles for React/TypeScript applications at Stello. It focuses on feature-first organization, maintainable imports, and pragmatic component patterns.

## Golden Rules

1. **Import Rule**: Always use `@/` path aliases, never relative paths (`../../`)
2. **Feature-First Rule**: Organize by feature/domain, not by technical layer
3. **Co-location Rule**: Keep tests, types, and code together within features
4. **Component Folder Rule**: Use `components/` subfolder only for features with 3+ components
5. **Barrel Export Rule**: Expose public API via `index.ts`, keep internals private
6. **Type Source Rule**: Use `@stello/shared-types` for backend entities, local types only for UI-specific concerns
7. **Service Layer Rule**: One service per external concern (API, third-party), shared across feature
8. **Hook Organization Rule**: Co-locate hooks with the feature that owns the logic
9. **Refactor Trigger**: When a feature exceeds 10 files in root, split into sub-features
10. **Simplicity Rule**: Start simple, add structure only when needed

## Import Patterns & Path Aliases

### Always Use @/ Alias

**Never use relative paths:**

```typescript
// ❌ BAD - Fragile, breaks when files move
import { useSegments } from '../../segments/hooks/useSegments';
import { contactsService } from '../../../shared/services/contactsService';
import { FilterCondition } from '../../types';

// ✅ GOOD - Clear, refactor-safe, consistent
import { useSegments } from '@/features/contacts/segments';
import { contactsService } from '@/features/contacts/shared/services/contactsService';
import type { FilterCondition } from '@/features/contacts/shared/types';
```

### Import Path Patterns

```typescript
// Intra-feature imports (within same feature)
import { useContacts } from '@/features/contacts/layout';
import { contactsService } from '@/features/contacts/shared/services/contactsService';
import type { FilterCondition } from '@/features/contacts/shared/types';

// Cross-feature imports (between features)
import { useAuth } from '@/features/auth/contexts/AuthContext';
import { DashboardLayout } from '@/features/dashboard/components/layout';

// Shared utilities and components
import { ApiClient } from '@/lib/apiClient';
import { Button } from '@/components/ui/button';

// External packages
import { useQuery } from '@tanstack/react-query';
import type { ContactResponse } from '@stello/shared-types';
```

### Type Imports

Always use `type` keyword for type-only imports:

```typescript
// ✅ GOOD - Explicit type-only imports
import type { ContactResponse } from '@stello/shared-types';
import type { FilterCondition } from '@/features/contacts/shared/types';

// ❌ BAD - Runtime import for types
import { ContactResponse } from '@stello/shared-types';
import { FilterCondition } from '@/features/contacts/shared/types';
```

## Feature-First Folder Organization

### Why Feature-First?

**Layer-first** (components/, hooks/, services/) becomes unscalable:
- Files far apart that change together
- Unclear feature boundaries
- Hard to split or refactor
- Difficult to understand dependencies

**Feature-first** groups by business domain:
- Related code stays together
- Clear boundaries between features
- Easy to refactor or extract
- Matches how you think about the product

### Structure Pattern

```
src/features/{feature}/
├── {sub-feature}/
│   ├── components/
│   │   ├── ComponentA.tsx
│   │   ├── ComponentB.tsx
│   │   └── index.ts          # Barrel export
│   ├── hooks/
│   │   ├── useFeatureData.ts
│   │   └── index.ts
│   ├── services/             # (if needed)
│   ├── constants/            # (if needed)
│   └── index.ts              # Sub-feature public API
├── shared/
│   ├── services/
│   │   ├── apiService.ts
│   │   └── index.ts
│   ├── types/
│   │   └── index.ts
│   └── hooks/                # Hooks used across sub-features
├── tests/                    # Feature-level integration tests
└── index.ts                  # Feature public API (minimal)
```

### Real Example: Contacts Feature

```
contacts/
├── segments/                 # Segment management sub-feature
│   ├── components/
│   │   ├── SegmentsList.tsx
│   │   ├── CreateSegmentModal.tsx
│   │   ├── EditSegmentModal.tsx
│   │   ├── ActiveFilterChips.tsx
│   │   └── index.ts
│   ├── hooks/
│   │   ├── useSegments.ts
│   │   ├── useSegment.ts
│   │   └── index.ts
│   └── index.ts
├── filters/                  # Filtering sub-feature
│   ├── components/
│   │   ├── ContactFilters.tsx
│   │   ├── ContactFilterButton.tsx
│   │   ├── FilterConditionModal.tsx
│   │   └── index.ts
│   └── index.ts
├── columns/                  # Column preferences sub-feature
│   ├── components/
│   │   └── ContactColumnEditor.tsx
│   ├── hooks/
│   │   └── useColumnPreferences.ts
│   ├── services/
│   │   └── columnPreferencesService.ts
│   ├── constants/
│   │   └── defaultColumns.ts
│   └── index.ts
├── layout/                   # Main layout & list sub-feature
│   ├── components/
│   │   ├── ContactsSection.tsx      # Main container
│   │   ├── ContactsTable.tsx         # List display
│   │   ├── ContactDetailSidebar.tsx # Detail view
│   │   └── index.ts
│   ├── hooks/
│   │   ├── useContacts.ts
│   │   ├── useContactCallHistory.ts
│   │   ├── useDebouncedValue.ts
│   │   └── index.ts
│   └── index.ts
├── import/                   # CSV import sub-feature
│   ├── components/
│   │   ├── CSVUploadModal.tsx
│   │   └── CSVColumnMapper.tsx
│   ├── hooks/
│   │   └── useCSVUploadFlow.ts
│   └── index.ts
├── batch/                    # Batch operations sub-feature
│   ├── components/
│   │   ├── BatchCallModal.tsx
│   │   └── BatchCallModal.css
│   └── index.ts
├── shared/                   # Cross-sub-feature code
│   ├── services/
│   │   ├── contactsService.ts       # API client
│   │   └── phoneNumbersService.ts
│   ├── types/
│   │   └── index.ts                 # Shared type definitions
│   └── hooks/
│       └── usePhoneNumbers.ts       # Used by multiple sub-features
├── tests/                    # Feature-level tests
│   ├── contacts.test.tsx
│   └── filtering.test.tsx
└── index.ts                  # Exports only ContactsSection (main entry)
```

### When to Create Sub-Features

**Start flat, split when needed:**

```
✅ GOOD - Small feature, stay flat:
auth/
├── components/
│   ├── LoginForm.tsx
│   ├── SignupForm.tsx
│   └── index.ts
├── contexts/
│   └── AuthContext.tsx
└── index.ts

✅ GOOD - Large feature, split by capability:
contacts/
├── segments/      # Domain: segment management
├── filters/       # Domain: filtering logic
├── columns/       # Domain: column preferences
├── layout/        # Domain: main display
└── shared/        # Cross-cutting within contacts
```

**Triggers to split:**
- 10+ files in feature root
- Multiple distinct business capabilities
- Different components serve different workflows
- Clear separation of concerns emerges

## Component Organization

### When to Use components/ Subfolder

**Use `components/` when:**
- 3+ components in a sub-feature
- Helps visually separate from hooks/services/types

**Skip `components/` when:**
- Only 1-2 components
- Keep it flat for simplicity

```
✅ GOOD - 1-2 components, stay flat:
batch/
├── BatchCallModal.tsx
├── BatchCallModal.css
└── index.ts

✅ GOOD - 3+ components, use subfolder:
segments/
├── components/
│   ├── SegmentsList.tsx
│   ├── CreateSegmentModal.tsx
│   ├── EditSegmentModal.tsx
│   ├── ActiveFilterChips.tsx
│   └── index.ts
├── hooks/
└── index.ts
```

### Component File Structure

```typescript
// ComponentName.tsx
import React, { useState } from 'react';
import { externalLibrary } from 'external-package';
import { sharedComponent } from '@/components/ui/button';
import { crossFeatureImport } from '@/features/other-feature';
import { intraFeatureImport } from '@/features/current-feature/sub-feature';
import type { TypeImport } from '@stello/shared-types';

// Types defined inline (component-specific)
interface ComponentNameProps {
  onAction: (id: string) => void;
  isLoading?: boolean;
}

// Helper functions (component-specific, not exported)
const formatData = (data: string): string => {
  return data.toUpperCase();
};

// Main component
export const ComponentName: React.FC<ComponentNameProps> = ({
  onAction,
  isLoading = false,
}) => {
  const [state, setState] = useState('');

  const handleClick = () => {
    onAction(state);
  };

  return (
    <div>
      {/* Component JSX */}
    </div>
  );
};
```

**Guidelines:**
- Component-specific interfaces inline (not in separate types file)
- Small helper functions inline (if > 20 lines, extract to utils)
- Single component per file
- Named exports (not default exports)
- Props interface always above component

### Component Size Guidelines

**Ideal:** 100-300 lines
**Warning:** 300-500 lines (consider splitting)
**Refactor:** 500+ lines (definitely split)

**Splitting strategies:**
1. Extract child components
2. Extract custom hooks
3. Extract helper functions to utils
4. Split into multiple related components

## Barrel Exports (index.ts)

### Multi-Level Export Strategy

Expose public API, hide implementation details:

```typescript
// ❌ BAD - No encapsulation, everything exported from root
contacts/
├── CreateSegmentModal.tsx
├── SegmentsList.tsx
├── useSegments.ts
├── types.ts
└── index.ts  // exports everything

// ✅ GOOD - Clear boundaries at each level
contacts/
├── segments/
│   ├── components/
│   │   ├── CreateSegmentModal.tsx
│   │   ├── SegmentsList.tsx
│   │   └── index.ts          // Export components
│   ├── hooks/
│   │   ├── useSegments.ts
│   │   └── index.ts          // Export hooks
│   └── index.ts              // Export public sub-feature API
└── index.ts                  // Export only ContactsSection
```

### Barrel Export Patterns

**Component-level barrel:**
```typescript
// segments/components/index.ts
export { CreateSegmentModal } from './CreateSegmentModal';
export { EditSegmentModal } from './EditSegmentModal';
export { SegmentsList } from './SegmentsList';
export { ActiveFilterChips, SaveToSegmentButton } from './ActiveFilterChips';
```

**Hook-level barrel:**
```typescript
// segments/hooks/index.ts
export { useSegments } from './useSegments';
export { useSegment } from './useSegment';
```

**Sub-feature barrel:**
```typescript
// segments/index.ts
export * from './components';
export * from './hooks';
// Don't export internal types or utilities
```

**Feature root barrel (minimal):**
```typescript
// contacts/index.ts
// Only export the main entry point
export { ContactsSection } from './layout';

// Don't export every sub-feature - they should be used via feature entry point
```

## React Hooks Organization

### Hook Location

**Co-locate hooks with the feature:**

```
✅ GOOD - Hook lives where it's used:
contacts/
├── layout/
│   ├── hooks/
│   │   └── useContacts.ts      # Used by layout components
│   └── components/
└── segments/
    ├── hooks/
    │   └── useSegments.ts      # Used by segment components
    └── components/

❌ BAD - Centralized hooks folder:
src/
├── hooks/
│   ├── useContacts.ts
│   ├── useSegments.ts
│   └── useFilters.ts           # Where do these belong?
└── features/
```

### Hook Naming

- Prefix with `use`: `useContacts`, `useSegments`
- Describe what it does: `useDebouncedValue`, `useColumnPreferences`
- Service-specific: `useCSVUploadFlow`

### When to Extract a Hook

Extract when:
- Logic reused across 2+ components
- Complex stateful logic (> 20 lines)
- Side effects need isolation (API calls, subscriptions)

Keep inline when:
- Single-component state management
- Simple derived values
- Basic event handlers

### Hook Dependencies

```typescript
// ✅ GOOD - Hook calls service layer
export const useContacts = (filters: ContactFilters = {}) => {
  const { organization } = useAuth();
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: ['contacts', organization?.id, filters],
    queryFn: () => contactsService.listContacts(filters),
  });
};

// ❌ BAD - Hook contains API logic directly
export const useContacts = () => {
  return useQuery({
    queryFn: () => fetch('/api/contacts').then(r => r.json()),
  });
};
```

### Hook Types

**Colocate hook-specific types with the hook file:**

```typescript
// ✅ GOOD - Hook types colocated with hook
// hooks/useAgentDraftPersistence.ts
interface UseAgentDraftPersistenceProps {
  agentId?: string;
  isCreateMode: boolean;
}

interface DraftState {
  agentName: string;
  // ...
}

export function useAgentDraftPersistence(
  props: UseAgentDraftPersistenceProps
): DraftState {
  // ...
}
```

```typescript
// ❌ BAD - Hook types in separate file
// types/hooks.ts
export interface UseAgentDraftPersistenceProps { ... }

// hooks/useAgentDraftPersistence.ts
import { UseAgentDraftPersistenceProps } from '../types/hooks';
```

**Why colocate?** Types define the hook's contract - they belong with the code they describe. When you refactor or move a hook, its types should move with it.

**Type Location Decision Matrix:**

| Type | Where to Put It |
|------|-----------------|
| Hook Props interface | In the hook file |
| Hook Return type | In the hook file |
| Domain types (used by 2+ files) | Central `types.ts` |
| Component props | In the component file |
| API types | `@stello/shared-types` |

## Service Layer (Frontend)

### Service Organization

**Pattern:** One service per external concern, shared across feature

```
contacts/
└── shared/
    └── services/
        ├── contactsService.ts       # API calls for contacts domain
        ├── phoneNumbersService.ts   # Phone number utilities
        └── index.ts
```

### Service Pattern

```typescript
// contactsService.ts
import { ApiClient } from '@/lib/apiClient';
import type { ContactResponse, ContactCreate } from '@stello/shared-types';
import type { ContactFilters } from '@/features/contacts/shared/types';

class ContactsService {
  private organizationId: string | null = null;

  setOrganizationId(orgId: string) {
    this.organizationId = orgId;
  }

  async listContacts(filters: ContactFilters = {}): Promise<ContactListResponse> {
    if (!this.organizationId) {
      throw new Error('Organization ID not set');
    }

    return await ApiClient.get<ContactListResponse>('/contacts', {
      organizationId: this.organizationId,
      ...filters,
    });
  }

  async createContact(data: ContactCreate): Promise<ContactResponse> {
    return await ApiClient.post<ContactResponse>('/contacts', data, {
      organizationId: this.organizationId,
    });
  }

  async deleteContact(contactId: string): Promise<void> {
    return await ApiClient.delete(`/contacts/${contactId}`, {
      organizationId: this.organizationId,
    });
  }
}

// Export singleton instance
export const contactsService = new ContactsService();
```

### Service Guidelines

- **Singleton pattern**: Export single instance, not class
- **Type-safe**: Use generated types from `@stello/shared-types`
- **Thin layer**: Just API calls, no business logic
- **Stateless**: Except for auth context (organizationId)
- **Error handling**: Let ApiClient handle errors, don't catch here

## Type Definitions

### Type Source Hierarchy

1. **Use `@stello/shared-types` for backend entities:**
```typescript
import type { ContactResponse, PhoneNumberInfo } from '@stello/shared-types';
```

2. **Create local types for frontend-specific concerns:**
```typescript
// contacts/shared/types/index.ts

// UI-specific types
export type ContactStatusValue = 'new' | 'contacted' | 'qualified' | 'unqualified';
export type ContactSourceValue = 'manual' | 'csv_import' | 'api' | 'integration';

// Frontend-only extensions
export interface ContactColumnPreferences extends UserColumnPreferences {
  columnDefinitions: ColumnDefinition[];  // UI-specific extension
}

// Filter types (frontend-only)
export interface FilterCondition {
  field: string;
  operator: string;
  value: string;
}

export interface ContactFilters {
  search?: string;
  status?: ContactStatusValue;
  source?: ContactSourceValue;
  customFilters?: FilterCondition[];
}
```

### When to Create Local Types

**Create local types for:**
- UI state and display logic
- Form data structures
- Filter/sort configurations
- Style mappings
- Derived/computed data structures

**DON'T create local types for:**
- Backend entities (use `@stello/shared-types`)
- API request/response shapes (use `@stello/shared-types`)
- Database model representations

### Type Co-location

```
✅ GOOD - Types in shared/ when used across sub-features:
contacts/
└── shared/
    └── types/
        └── index.ts           # FilterCondition, ContactFilters

✅ GOOD - Types inline when component-specific:
ContactColumnEditor.tsx:
  interface ContactColumnEditorProps { ... }
  interface ColumnCategory { ... }

❌ BAD - Global types folder:
src/
└── types/
    └── contacts.ts           # Too far from usage
```

## Testing Co-location

Place tests close to what they test:

```
contacts/
├── segments/
│   ├── components/
│   │   └── SegmentsList.tsx
│   └── tests/
│       └── SegmentsList.test.tsx    # Component tests
├── layout/
│   └── hooks/
│       ├── useContacts.ts
│       └── useContacts.test.ts      # Hook tests
└── tests/
    └── contacts-flow.test.tsx       # Integration tests
```

**Test organization:**
- Unit tests: Next to component/hook (`*.test.tsx`, `*.test.ts`)
- Integration tests: Feature `tests/` folder
- E2E tests: Root `playwright/` folder by feature

## Decision Frameworks

### Should I create a new sub-feature?

```
├─ < 10 files in feature root?
│  └─ YES → Keep flat, no sub-features yet
│  └─ NO → Consider sub-features ↓
├─ Multiple distinct business capabilities?
│  └─ YES → Split into sub-features
│  └─ NO → Keep as single feature
└─ Would sub-features have clear boundaries?
   └─ YES → Create sub-features
   └─ NO → Refactor to clarify domains first
```

### Should I use a components/ subfolder?

```
├─ 3+ components in this sub-feature?
│  └─ YES → Use components/ subfolder
│  └─ NO → Keep components flat
```

### Should I extract a custom hook?

```
├─ Logic used in 2+ components?
│  └─ YES → Extract hook
│  └─ NO ↓
├─ Complex stateful logic (> 20 lines)?
│  └─ YES → Extract hook
│  └─ NO ↓
├─ Side effects need isolation?
│  └─ YES → Extract hook
│  └─ NO → Keep inline
```

### Should I create a local type or use @stello/shared-types?

```
├─ Type represents backend entity?
│  └─ YES → Use @stello/shared-types
│  └─ NO ↓
├─ Type is API request/response?
│  └─ YES → Use @stello/shared-types
│  └─ NO ↓
├─ Type is UI-specific (filters, display, state)?
│  └─ YES → Create local type in shared/types
│  └─ NO → Reevaluate what this type represents
```

## Anti-Patterns

### 1. Relative Path Imports

```typescript
// ❌ NEVER DO THIS
import { useSegments } from '../../segments/hooks/useSegments';
import { ContactFilters } from '../types';

// ✅ ALWAYS DO THIS
import { useSegments } from '@/features/contacts/segments';
import type { ContactFilters } from '@/features/contacts/shared/types';
```

### 2. Layer-First Organization

```typescript
// ❌ BAD - Organized by technical layer
src/
├── components/
│   ├── ContactsList.tsx
│   ├── SegmentsList.tsx
│   └── UserProfile.tsx
├── hooks/
│   ├── useContacts.ts
│   └── useAuth.ts
└── services/
    ├── contactsService.ts
    └── authService.ts

// ✅ GOOD - Organized by feature/domain
src/features/
├── contacts/
│   ├── layout/
│   │   └── components/ContactsList.tsx
│   ├── segments/
│   │   └── components/SegmentsList.tsx
│   └── shared/
│       └── services/contactsService.ts
└── auth/
    ├── components/UserProfile.tsx
    ├── hooks/useAuth.ts
    └── services/authService.ts
```

### 3. Overly Deep Nesting

```typescript
// ❌ BAD - Too many levels
src/features/contacts/management/segments/ui/components/lists/SegmentsList.tsx

// ✅ GOOD - 3 levels max
src/features/contacts/segments/components/SegmentsList.tsx
```

### 4. God Components

```typescript
// ❌ BAD - 800-line component doing everything
export const ContactsPage = () => {
  // 50 lines of state
  // 200 lines of handlers
  // 400 lines of JSX
  // Manages segments, filters, columns, calls, imports...
};

// ✅ GOOD - Composition of focused components
export const ContactsSection = () => {
  return (
    <DashboardLayout>
      <ContactFilters {...filterProps} />
      <ContactsTable {...listProps} />
      <ContactDetailSidebar {...sidebarProps} />
    </DashboardLayout>
  );
};
```

### 5. Business Logic in Components

```typescript
// ❌ BAD - API logic in component
export const ContactsList = () => {
  const [contacts, setContacts] = useState([]);

  useEffect(() => {
    fetch('/api/contacts')
      .then(r => r.json())
      .then(setContacts);
  }, []);

  return <div>{/* render */}</div>;
};

// ✅ GOOD - Service layer + hook
export const ContactsList = () => {
  const { data: contacts } = useContacts();
  return <div>{/* render */}</div>;
};
```

### 6. Duplicate Type Definitions

```typescript
// ❌ BAD - Duplicating backend types
interface Contact {  // Already exists in @stello/shared-types!
  id: string;
  name: string;
  email: string;
}

// ✅ GOOD - Use generated types
import type { ContactResponse } from '@stello/shared-types';
```

## Summary: Quick Reference

| Concern | Pattern | Example |
|---------|---------|---------|
| Imports | Always `@/` alias | `@/features/contacts/segments` |
| Organization | Feature-first | `features/contacts/segments/components/` |
| Component Folder | 3+ components | `segments/components/` vs `batch/BatchModal.tsx` |
| Types | Backend: shared-types, UI: local | `ContactResponse` vs `FilterCondition` |
| Hooks | Co-locate with feature | `contacts/segments/hooks/useSegments.ts` |
| Services | In shared/ | `contacts/shared/services/contactsService.ts` |
| Tests | Next to code | `SegmentsList.test.tsx` near `SegmentsList.tsx` |
| Exports | Multi-level barrels | `index.ts` at each level |

## Resources

- **Type Generation**: See [CLAUDE.md - Type Safety](../CLAUDE.md#type-safety--api-data-conversion)
- **Backend Patterns**: See [Service Architecture](service-architecture.md) for comparison
- **Testing**: See [Frontend E2E Testing](frontend-e2e-testing.md) for Playwright patterns
