---
name: clean-code
description: Apply Stello AI clean code standards for Python/FastAPI backends and React frontends. Use when writing new code, reviewing code, making architecture decisions, or when the user asks about code style, patterns, or best practices.
---

# Stello AI Clean Code Standards

## When This Skill Applies

- Writing new features or services
- Reviewing code for style/pattern violations
- Making architecture decisions
- Refactoring existing code
- Adding external integrations

## Golden Rules

1. **Orchestrator Rule**: Start with router → service. Add orchestrator only when coordinating multiple services.
2. **Size Rule**: Max 500 LOC or 8 operations per service
3. **External API Rule**: Implement compensation for operations that cost money/quota
4. **Dependency Rule**: One-way flow - Features → Integrations → External SDKs
5. **Integration Rule**: Keep integrations thin (SDK wrappers only)
6. **Abstraction Rule**: Don't abstract until you have 2+ implementations

## Reference Guides

See the full documentation in `CLEAN_CODE_GUIDE/`:

### Backend
- [Service Architecture](../../CLEAN_CODE_GUIDE/service-architecture.md) - Service guardrails, orchestration patterns
- [Database Patterns](../../CLEAN_CODE_GUIDE/database-patterns.md) - Transaction boundaries, async pitfalls
- [API Design Patterns](../../CLEAN_CODE_GUIDE/api-design-patterns.md) - Router patterns, orchestration decisions
- [Directory Organization](../../CLEAN_CODE_GUIDE/directory-organization.md) - File structure, model placement

### Frontend
- [Frontend Architecture](../../CLEAN_CODE_GUIDE/frontend-architecture.md) - React patterns, import aliases
- [ReactFlow Patterns](../../CLEAN_CODE_GUIDE/reactflow-patterns.md) - Flow diagram patterns

### External Integration
- [Integration Patterns](../../CLEAN_CODE_GUIDE/integration-patterns.md) - External APIs, thin wrappers
- [Third-Party Workflow](../../CLEAN_CODE_GUIDE/third-party-integration-workflow.md) - Mock → test → VCR → production

### Testing
- [Testing Style Guide](../../CLEAN_CODE_GUIDE/TESTING_STYLE_GUIDE.md) - Backend pytest patterns
- [Frontend E2E Testing](../../CLEAN_CODE_GUIDE/frontend-e2e-testing.md) - Playwright patterns

### Reference
- [Decision Frameworks](../../CLEAN_CODE_GUIDE/decision-frameworks.md) - When to use what
- [Anti-Patterns](../../CLEAN_CODE_GUIDE/anti-patterns.md) - Common mistakes to avoid
- [Feature Flags](../../CLEAN_CODE_GUIDE/feature-flags.md) - Feature flag patterns
