# Python Clean Code Guide for Stello AI

This guide documents clean code principles learned from refactoring the Retell template system. It focuses on industry-standard patterns for Python/FastAPI applications, avoiding over-engineering while maintaining maintainability.

## Quick Navigation

### 🏗️ Core Architecture

- **[Service Architecture](service-architecture.md)** - Service guardrails, orchestration patterns, three-layer design (Backend)
- **[Database Patterns](database-patterns.md)** - Transaction boundaries, commit/refresh patterns, atomic operations, async pitfalls (Backend)
- **[Frontend Architecture](frontend-architecture.md)** - React patterns, import aliases, feature-first organization (Frontend)
- **[Directory Organization](directory-organization.md)** - File structure, vertical slices, model placement (Backend)
- **[API Design Patterns](api-design-patterns.md)** - Router patterns, orchestration decisions, frontend vs backend

### 🔌 External Integration

- **[Third-Party Integration Workflow](third-party-integration-workflow.md)** - Complete workflow for adding new integrations: development with mocks → testing → VCR validation → production
- **[Integration Patterns](integration-patterns.md)** - External APIs, thin wrappers, compensation patterns
- **[Error Handling & Cleanup](error-handling.md)** - Compensation patterns, external API failures, transaction boundaries

### 🧪 Development Practices

- **[Testing Style Guide](TESTING_STYLE_GUIDE.md)** - Backend testing patterns (pytest, factories, E2E vs integration)
- **[Frontend E2E Testing](frontend-e2e-testing.md)** - Playwright testing patterns (helpers, selectors, data factories)
- **[Decision Frameworks](decision-frameworks.md)** - When to use what pattern, decision matrices
- **[Anti-Patterns](anti-patterns.md)** - Common mistakes to avoid, red flags

## Core Principles Overview

### Backend Service Guardrails

- **Maximum Size**: 500 lines of code per service
- **Maximum Scope**: 8 public operations per service
- **Single Domain**: One business capability per service
- **Thin Orchestration**: Coordinate operations, don't implement complex logic

### Frontend Organization Principles

- **Import Rule**: Always use `@/` path aliases, never relative paths (`../../`)
- **Feature-First**: Organize by domain/feature, not technical layer (components/, hooks/)
- **Co-location**: Keep tests, types, and code together within features
- **Type Source**: Use `@stello/shared-types` for backend entities, local types for UI concerns
- **Simplicity**: Start simple, add structure only when needed

### Service Architecture Patterns

**Default Pattern** (start here):

```
Router Layer (HTTP) → Service (domain logic)
```

**With Orchestrator** (when you have multiple services that coordinate):

```
Router Layer (HTTP) → Orchestrator (coordination) → Specialized Services (domain logic)
```

**Key Rule**: Only add orchestrator when you have actual coordination needs between services.

### Integration Layer Rules

- Features can import integrations directly
- Keep integrations thin (SDK wrappers only)
- One-way dependency flow: Features → Integrations → External SDKs
- Avoid ports/adapters pattern for single vendors

## Golden Rules Summary

1. **Orchestrator Rule**: Start with router → service (no orchestrator). Only add orchestrator when you have multiple services that need coordination.
2. **Size Rule**: If service exceeds 500 LOC or 8 operations, split by domain capability
3. **External API Rule**: If operation creates external resources that cost money/quota, implement compensation
4. **Dependency Rule**: One-way flow only - Features → Integrations → External SDKs
5. **Integration Rule**: Keep integrations thin (SDK wrappers only) - no business logic
6. **Abstraction Rule**: Don't abstract until you have 2+ implementations
7. **Orchestration Rule**: If coordination method has >20 lines, you're doing business logic
8. **API Design Rule**: Each endpoint should be independently useful - avoid orchestration APIs
9. **Coordination Rule**: Start with frontend orchestration for user workflows
10. **Transformation Rule**: External API transformations belong in Pydantic schemas with factory methods, not scattered in service layers

## Getting Started

### For Backend Development
1. **New to the codebase?** Start with [Service Architecture](service-architecture.md) to understand the layered approach
2. **Adding new features?** Check [Directory Organization](directory-organization.md) for proper file placement
3. **Building APIs?** Review [API Design Patterns](api-design-patterns.md) for the right orchestration approach
4. **Integrating external services?** See [Integration Patterns](integration-patterns.md) for best practices

### For Frontend Development
1. **New to the codebase?** Start with [Frontend Architecture](frontend-architecture.md) to understand React patterns
2. **Organizing features?** Learn the feature-first pattern and when to split sub-features
3. **Import confusion?** Always use `@/` aliases, never relative paths
4. **Type definitions?** Use `@stello/shared-types` for backend entities, create local types for UI concerns

### For All Developers
5. **Need to make decisions?** Use [Decision Frameworks](decision-frameworks.md) for guidance
6. **Writing tests?** See [Testing Style Guide](TESTING_STYLE_GUIDE.md) (backend) or [Frontend E2E Testing](frontend-e2e-testing.md)

## Why These Patterns?

These patterns emerged from real refactoring experience at Stello AI, focusing on:

- **Maintainability**: Clear boundaries and responsibilities
- **Testability**: Simple, mockable interfaces
- **Team Velocity**: Independent development and deployment
- **System Resilience**: Graceful failure handling
- **Simplicity**: Right-sized abstractions, not over-engineering

Each focused guide addresses specific concerns while maintaining consistency with the overall architectural vision.
