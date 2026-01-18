# Service Architecture Patterns

This guide covers service design patterns, guardrails, and orchestration strategies for maintaining clean, maintainable services.

## Service Guardrails

**Strict Limits for Maintainable Services:**

- **Maximum Size**: 500 lines of code per service
- **Maximum Scope**: 8 public operations per service
- **Single Domain**: One business capability per service
- **Thin Orchestration**: Coordinate operations, don't implement complex logic

**Why These Limits?** 500 LOC keeps services focused, 8 operations prevents feature creep, single domain ensures cohesion, thin orchestration avoids heavy business logic.

**Measuring Service Health:**

```python
# ✅ GOOD: Within guardrails
class TemplateService:  # ~200 LOC, 5 public methods, single domain
    async def load_template(self, name: str): ...         # Public #1
    async def customize_template(self, template, params): ...  # Public #2
    async def validate_template(self, template): ...      # Public #3
    async def save_template(self, template, org_id): ...  # Public #4
    async def delete_template(self, template_id): ...     # Public #5

    # Private helper methods don't count toward the 8-operation limit
    def _apply_customization(self, template, key, value): ...
    def _validate_required_fields(self, template): ...

# ❌ BAD: Exceeds guardrails
class MegaTemplateService:  # 800+ LOC, 12+ operations, multiple domains
    # Handles templates, agents, flows, analytics - violates single domain rule
```

## Service Architecture Patterns (Start Simple, Add Complexity as Needed)

### Pattern 0: No Orchestrator (Router → Direct Service Calls) - START HERE

**When to Use**: This is your DEFAULT starting point. Use this pattern unless you have actual coordination needs.

**Characteristics**:

- Router calls specialized service directly
- No orchestrator layer
- Single service handles the domain
- Simplest architecture with least code

**Example - Single Service Domain:**

```python
# Feature structure (no orchestrator)
features/templates/
├── router.py                 # Calls service directly
├── template_service.py       # Single service handles everything
├── schemas.py
└── models.py

# router.py
from app.features.templates.template_service import get_template_service

@router.post("/templates")
async def create_template(request: CreateTemplateRequest, db: DatabaseDep):
    """No orchestrator needed - call service directly"""
    service = get_template_service()
    return await service.create_template(request, db)

@router.get("/templates/{template_id}")
async def get_template(template_id: str, db: DatabaseDep):
    """Direct service call - clean and simple"""
    service = get_template_service()
    return await service.get_template(template_id, db)

# template_service.py
class TemplateService:
    """Single service handles entire domain - no coordination needed"""

    async def create_template(self, request: CreateTemplateRequest, db: AsyncSession):
        # All business logic lives here
        template = Template(
            id=str(uuid.uuid4()),
            name=request.name,
            content=request.content,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    async def get_template(self, template_id: str, db: AsyncSession):
        return await db.get(Template, template_id)
```

**✅ Advantages:**

- Least code to maintain
- Direct, easy to understand
- No unnecessary layers
- Fast development velocity

**❌ When to Evolve**: Add orchestrator only when you split into multiple specialized services that need coordination.

---

### Pattern 1: Thin Orchestrator (Single Domain, Multiple Specialized Services)

**When to Use**: You've split a domain into multiple specialized services (CRUD, CSV, Lifecycle) that need coordination.

**Characteristics**:

- Multiple specialized services per domain
- Thin orchestrator coordinates them
- Some cross-service workflows
- Backward compatibility with existing imports

**Example - Multiple Coordinated Services:**

```python
# Feature structure (with orchestrator)
features/contacts/
├── router.py                      # Calls orchestrator
├── service.py                     # Thin orchestrator
├── contact_crud_service.py        # CRUD operations
├── contact_csv_service.py         # CSV import/export
├── contact_lifecycle_service.py   # Status management
├── schemas.py
└── models.py

# router.py
from app.features.contacts.service import get_contact_service

@router.post("/contacts")
async def create_contact(request: ContactCreate, db: DatabaseDep):
    """Router still calls single entry point (orchestrator)"""
    service = get_contact_service()
    return await service.create_contact(request, db)

# service.py (Thin Orchestrator)
class ContactService:
    """Orchestrator coordinates multiple specialized services"""

    def __init__(self):
        self.crud = ContactCRUDService()
        self.csv = ContactCSVService(self.crud)  # ← CSV depends on CRUD
        self.lifecycle = ContactLifecycleService()

    # Simple delegation (most methods)
    async def create_contact(self, request, db):
        return await self.crud.create_contact(request, db)

    # Real coordination (some methods)
    async def update_from_call_analysis(self, contact_id, org_id, analysis, db):
        """Actual coordination: fetch from CRUD, process via Lifecycle"""
        contact = await self.crud.get_contact(contact_id, org_id, db)
        if not contact:
            return None
        return await self.lifecycle.update_from_analysis(contact, analysis, db)
```

**✅ When This Makes Sense:**

- Multiple specialized services with different responsibilities
- CSV service needs CRUD service (dependency injection)
- Some workflows span multiple services
- Maintains backward compatibility

**❌ Anti-Pattern - Architecture Sinkhole**: If 80%+ of orchestrator methods are simple pass-through delegation with no coordination logic, the orchestrator violates the **80-20 Rule** and should be removed.

**The 80-20 Rule (Industry Best Practice):**
- ✅ **20% pass-through methods are acceptable** (e.g., some simple delegations for consistency)
- ❌ **80%+ pass-through methods = anti-pattern** (orchestrator adds no value, creates unnecessary indirection)

**How to Measure:**
```
Coordination Methods = Methods that coordinate 2+ services or have real business logic
Pass-Through Methods = Methods that just return await self.service.method()

Ratio = Pass-Through Count / Total Methods
- If Ratio < 20% → ✅ GOOD, keep orchestrator
- If Ratio > 80% → ❌ BAD, remove thin delegation methods
```

**Example - ContactService Refactoring:**
```python
# ❌ BEFORE: 13 pass-throughs + 3 coordination = 81% sinkhole
class ContactService:
    async def create_contact(self, ...): return await self.crud.create_contact(...)  # Pass-through
    async def get_contact(self, ...): return await self.crud.get_contact(...)        # Pass-through
    async def list_segments(self, ...): return await self.segment.list_segments(...) # Pass-through
    # ... 10 more pass-throughs ...
    async def list_contacts_with_filters(self, ...): # ✓ Real coordination

# ✅ AFTER: Only coordination methods remain
class ContactService:
    async def list_contacts_with_filters(self, ...): # Coordinates segment + CRUD
    async def archive_custom_field(self, ...):       # Coordinates CRUD + cleanup
    async def delete_custom_field(self, ...):        # Coordinates CRUD + schema
```

**Router Pattern When Removing Pass-Throughs:**
```python
# Call orchestrator only for complex operations
service = get_contact_service()
contacts = await service.list_contacts_with_filters(...)  # ✓ Multi-service coordination

# Call specialized services directly for simple CRUD
crud = get_contact_crud_service()
contact = await crud.get_contact(...)                    # ✓ Single service, direct call
```

---

### Pattern 2: Use-Case Service Pattern (Single Service with Private Methods)

**When to Use**: Single service with complex internal workflows that don't need to be split into separate services.

**Characteristics**:

- Single service class handles entire domain
- Private methods organize internal complexity
- Public methods coordinate private operations
- No need for separate specialized services

```python
class TemplateService:  # ~180 LOC, 4 operations, single domain
    """Single service with private methods for internal organization"""

    async def create_conversation_flow(self, template_name: str, customization: dict):
        """Public method coordinates private operations"""
        template = await self._load_template(template_name)
        customized = self._apply_customizations(template, customization)
        validated = self._validate_template(customized)
        return await self._save_template_config(validated)

    # Private methods handle database, file operations, business logic
    async def _save_template_config(self, data: dict, db: AsyncSession): ...
    def _load_template(self, name: str) -> dict: ...
    def _apply_customizations(self, template: dict, customizations: dict) -> dict: ...
```

**✅ Advantages:**

- All logic in one place
- No coordination between services needed
- Private methods keep code organized
- Still under 500 LOC

**❌ When to Evolve**: When service exceeds 500 LOC or has >8 operations, split into specialized services (Pattern 1).

---

### Pattern 3: Service Composition (Large Domains with Multiple Specialized Services)

**When to Use**: Domain has grown large (would exceed 500 LOC as single service) and needs multiple specialized services.

```python
class TemplateService:  # Main orchestrator
    def __init__(self):
        self.loader = TemplateLoadingService()     # <500 LOC, <8 operations
        self.flow_creator = ConversationFlowService()  # <500 LOC, <8 operations
        self.agent_creator = AgentCreationService()    # <500 LOC, <8 operations

    async def create_complete_agent_setup(self, request: AgentRequest):
        """Thin orchestration - delegates to focused domain services"""
        template = await self.loader.load_and_customize(request.template_name, request.customizations)
        flow = await self.flow_creator.create_flow(template, request.organization_id)
        agent = await self.agent_creator.create_agent(flow.id, request.voice_settings)
        return CompleteAgentSetup(agent=agent, flow=flow, template=template)
```

**Rules:** Split by business capability (not technical layers), orchestrator provides thin coordination, domain services never call each other directly.

## Orchestration Rules for External APIs

**Orchestration Rule**: If service method has >5 lines of field mapping or object building, extract to integration schema.

**Thin Integration Rule**: Integration schemas handle ALL external API formatting - services only orchestrate.

**✅ Thin Orchestration:**

```python
# Service: Pure coordination
async def create_event_type(self, request: CreateEventTypeRequest):
    payload = CalComEventTypePayload.from_request(request, calendar_type="google")
    return await self.cal_com.create_event_type(payload.to_api_dict())
```

**❌ Fat Orchestration:**

```python
# Service doing transformation work - violates thin orchestration
async def create_event_type(self, request: CreateEventTypeRequest):
    # 15+ lines of field mapping - belongs in integration schema!
    cal_com_data = {
        "title": request.title,
        "length": request.duration_minutes,
        "customName": request.custom_name or "Default template",
        "destinationCalendar": {"externalId": request.calendar_id, "integration": "google"},
        # ... more transformations
    }
    return await self.cal_com.create_event_type(cal_com_data)
```

## Service Instantiation & Session Management Patterns

Services can be instantiated using two patterns: stateless factory functions or stateful dependency injection. Choose based on service complexity and session usage patterns.

### Pattern 1: Stateless Factory Functions (Simple Services)

**When to Use:**
- Service has 1-4 methods
- Methods are mostly independent
- Simple CRUD operations
- No shared state management needed

**Example:**

```python
# service.py
class TemplateService:
    async def create_template(self, data: dict, db: AsyncSession) -> Template:
        template = Template(**data)
        db.add(template)
        await db.commit()
        return template

    async def get_template(self, template_id: str, db: AsyncSession) -> Template | None:
        return await db.get(Template, template_id)

# Factory function (no DI)
def get_template_service() -> TemplateService:
    return TemplateService()

# Router usage
@router.post("/templates")
async def create_template(data: TemplateCreate, db: DatabaseDep):
    service = get_template_service()
    return await service.create_template(data, db)
```

**Pros:**
- ✅ Simple to understand
- ✅ No DI overhead
- ✅ Easy to test (just instantiate)

**Cons:**
- ❌ Session parameter on every method
- ❌ Repetitive signatures for large services
- ❌ No centralized transaction management

### Pattern 2: Stateful Dependency Injection (Complex Services)

**When to Use:**
- Service has 5+ methods
- All methods need database access
- CRUD pattern with consistent session usage
- Complex orchestration requiring transaction management

**Example:**

```python
# service.py - Stateful with DI
class WorkflowCRUDService:
    """Service with session managed through DI"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_workflow(self, data: WorkflowCreate) -> Workflow:
        workflow = Workflow(**data.model_dump())
        self.session.add(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow

    async def get_workflow(self, workflow_id: str) -> Workflow | None:
        # Uses self.session - no parameter needed
        return await self.session.get(Workflow, workflow_id)

    async def list_workflows(self, org_id: str) -> list[Workflow]:
        # Clean method signature - session is implicit
        stmt = select(Workflow).where(Workflow.organization_id == org_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_workflow(self, workflow_id: str, data: WorkflowUpdate) -> Workflow | None:
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(workflow, key, value)
        self.session.add(workflow)
        await self.session.commit()
        return workflow

    async def delete_workflow(self, workflow_id: str) -> bool:
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return False
        await self.session.delete(workflow)
        await self.session.commit()
        return True

    # ... 3+ more CRUD methods

# Dependency provider with DI
def get_workflow_crud_service(
    session: AsyncSession = Depends(get_db)
) -> WorkflowCRUDService:
    return WorkflowCRUDService(session)

# Router usage - clean injection
@router.post("/workflows")
async def create_workflow(
    data: WorkflowCreate,
    service: WorkflowCRUDService = Depends(get_workflow_crud_service)
):
    return await service.create_workflow(data)

@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    service: WorkflowCRUDService = Depends(get_workflow_crud_service)
):
    return await service.get_workflow(workflow_id)
```

**Pros:**
- ✅ Clean method signatures (no session parameter)
- ✅ Centralized session management
- ✅ FastAPI handles injection automatically
- ✅ Easy to mock entire service in tests
- ✅ Scales well with large services (8+ methods)

**Cons:**
- ❌ Slightly more setup code
- ❌ Need to understand FastAPI DI system
- ❌ Session lifecycle tied to request scope

### Decision Framework

| Criteria | Stateless Factory | Stateful DI |
|----------|------------------|-------------|
| **Method count** | 1-4 methods | 5+ methods |
| **Session usage** | Occasional | Every method |
| **Service pattern** | Utility, helper | CRUD, orchestrator |
| **Complexity** | Simple | Complex |
| **Testability** | Direct instantiation | Mock injection |

### Migration Guide: Factory → DI Pattern

When a service grows beyond 4 methods and most methods need database access, consider migrating to the stateful DI pattern:

**Step 1: Add session to __init__**
```python
# Before: No constructor
class WorkflowCRUDService:
    async def create(self, data, db: AsyncSession):
        pass

# After: Store session
class WorkflowCRUDService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data):  # No db parameter
        pass
```

**Step 2: Remove session parameters from methods**
```python
# Before: Session on every method
async def create_workflow(self, data: WorkflowCreate, db: AsyncSession):
    db.add(workflow)
    await db.commit()

# After: Use self.session
async def create_workflow(self, data: WorkflowCreate):
    self.session.add(workflow)
    await self.session.commit()
```

**Step 3: Update dependency provider**
```python
# Before: Factory with no DI
def get_workflow_crud_service() -> WorkflowCRUDService:
    return WorkflowCRUDService()

# After: DI provider
def get_workflow_crud_service(
    session: AsyncSession = Depends(get_db)
) -> WorkflowCRUDService:
    return WorkflowCRUDService(session)
```

**Step 4: Update router calls**
```python
# Before: Manual instantiation
@router.post("/workflows")
async def create_workflow(data: WorkflowCreate, db: DatabaseDep):
    service = get_workflow_crud_service()
    return await service.create_workflow(data, db)

# After: FastAPI DI injection
@router.post("/workflows")
async def create_workflow(
    data: WorkflowCreate,
    service: WorkflowCRUDService = Depends(get_workflow_crud_service)
):
    return await service.create_workflow(data)
```

### Testing Patterns

**Factory Pattern Testing:**
```python
async def test_create_template(db_transaction: AsyncSession):
    service = TemplateService()  # Direct instantiation
    result = await service.create_template(data, db_transaction)
    assert result.name == "Test"
```

**DI Pattern Testing:**
```python
async def test_create_workflow(db_transaction: AsyncSession):
    # Inject session via constructor
    service = WorkflowCRUDService(db_transaction)
    result = await service.create_workflow(data)
    assert result.name == "Test"
```

## Service Architecture Evolution & Scaling Patterns

**Key Insight:** Pyramidal service architectures naturally evolve through predictable growth phases. Understanding these phases helps teams make informed decisions about when and how to restructure their service organization.

### Evolution Timeline: From Simple to Complex

**Phase 1: Simple Pyramid (5-8 Services) ✅ IDEAL**

This is where most domains should start and many should stay:

```python
# Example: voice_agents/ (Current Stello State)
voice_agents/
├── service.py                    # Orchestrator: ~80 LOC, 5 methods
├── creation_service.py           # Agent CRUD operations
├── configuration_service.py      # Settings & configuration
├── deletion_service.py           # Cleanup operations
├── retrieval_service.py          # Data fetching
└── profile_update_service.py     # Profile management

# Thin orchestrator - pure delegation
class VoiceAgentService:
    def __init__(self):
        self.creation = CreationService()
        self.config = ConfigurationService()
        self.deletion = DeletionService()
        self.retrieval = RetrievalService()
        self.profile = ProfileUpdateService()

    # Simple delegation methods (1-2 lines each)
    async def create_agent(self, config):
        return await self.creation.create_agent(config)

    async def update_config(self, agent_id, settings):
        return await self.config.update_config(agent_id, settings)
```

**Phase 2: Natural Growth (10+ Services) ✅ STILL GOOD**

As domains mature, they naturally accumulate more specialized operations:

```python
# Expanded voice_agents/ (Hypothetical Growth)
voice_agents/
├── service.py                    # Orchestrator: ~150 LOC, 10 methods
├── creation_service.py           # Agent CRUD
├── configuration_service.py      # Settings & config
├── deletion_service.py           # Cleanup operations
├── retrieval_service.py          # Data fetching
├── profile_update_service.py     # Profile management
├── analytics_service.py          # NEW: Performance tracking
├── backup_service.py             # NEW: Agent backup/restore
├── testing_service.py            # NEW: A/B testing agents
├── cloning_service.py            # NEW: Agent duplication
└── monitoring_service.py         # NEW: Health monitoring

# Orchestrator grows but stays thin (pure delegation)
class VoiceAgentService:  # 150 LOC - still acceptable
    def __init__(self):
        # Initialize 10+ services
        self.creation = CreationService()
        self.config = ConfigurationService()
        # ... 8 more services

    # 10+ simple delegation methods (still 1-2 lines each)
    async def create_agent(self, config):
        return await self.creation.create_agent(config)

    async def clone_agent(self, agent_id):
        return await self.cloning.clone_agent(agent_id)

    async def setup_monitoring(self, agent_id):
        return await self.monitoring.setup_monitoring(agent_id)
    # ... 7 more simple delegations
```

**⚠️ Phase 3: Complexity Emergence (RESTRUCTURE NEEDED)**

The breaking point occurs when **workflows span multiple services**, not when method count gets high:

```python
# Orchestrator starts accumulating complex business logic
class VoiceAgentService:  # 300+ LOC - getting thick!

    async def create_production_ready_agent(self, config):
        """❌ COMPLEX WORKFLOW spanning multiple services"""
        async with db.transaction():
            # 1. Create base agent
            agent = await self.creation.create_agent(config.base)

            # 2. Apply production configurations
            await self.config.apply_production_settings(agent.id, config.prod_settings)

            # 3. Set up comprehensive monitoring
            monitoring_config = self._build_monitoring_config(agent.id, config.monitoring)
            await self.monitoring.setup_agent_monitoring(agent.id, monitoring_config)

            # 4. Create backup schedule
            backup_schedule = self._calculate_backup_frequency(config.criticality)
            await self.backup.schedule_automatic_backups(agent.id, backup_schedule)

            # 5. Initialize analytics tracking
            analytics_config = self._build_analytics_config(agent, config.tracking)
            await self.analytics.setup_tracking(agent.id, analytics_config)

            # 6. Run production readiness tests
            test_suite = self._select_test_suite(config.environment)
            test_results = await self.testing.run_production_tests(agent.id, test_suite)

            if not test_results.all_passed:
                await self._handle_test_failures(agent.id, test_results)
                raise ProductionReadinessError(test_results.failures)

            # 7. Final validation and cleanup
            final_validation = await self._validate_production_setup(agent.id)

            return ProductionReadyAgent(agent, test_results, final_validation)
```

### Decision Framework: When to Restructure

**🟢 Keep Current Structure When:**

- Orchestrator methods are 1-3 lines of pure delegation
- Each specialized service handles distinct business operations
- Services rarely need to coordinate with each other
- Team ownership boundaries are clear per service
- Orchestrator stays under 200 LOC total

**🟡 Consider Restructuring When:**

- 3+ methods in orchestrator involve complex multi-service workflows
- Orchestrator methods average 5+ lines with business logic
- You're adding helper methods to the orchestrator (`_build_config`, `_validate_setup`)
- Services frequently need to coordinate in specific patterns

**🔴 Definitely Restructure When:**

- Orchestrator exceeds 200-300 LOC
- Complex workflows are becoming the norm rather than simple operations
- You're seeing clear domain clusters that rarely interact
- New team members struggle to understand the orchestrator's responsibilities

### Restructuring Strategy: Domain Clustering

When restructuring becomes necessary, group services by natural business domains:

```python
# BEFORE: Single large orchestrator
voice_agents/
├── service.py                    # 300+ LOC, complex workflows
├── creation_service.py
├── configuration_service.py
├── deletion_service.py
├── retrieval_service.py
├── profile_update_service.py
├── analytics_service.py
├── backup_service.py
├── testing_service.py
├── cloning_service.py
└── monitoring_service.py

# AFTER: Domain-clustered architecture
voice_agents/
├── core/                         # Basic agent lifecycle
│   ├── service.py               # Orchestrator for core operations only
│   ├── creation_service.py
│   ├── deletion_service.py
│   └── retrieval_service.py
│
├── operations/                   # Production operations
│   ├── service.py               # Orchestrator for ops workflows
│   ├── monitoring_service.py
│   ├── backup_service.py
│   └── testing_service.py
│
├── customization/               # Agent personalization
│   ├── service.py              # Orchestrator for customization
│   ├── configuration_service.py
│   ├── profile_update_service.py
│   └── cloning_service.py
│
└── service.py                   # TOP-LEVEL: Cross-domain workflows only
```

**Ultra-Thin Top-Level Orchestrator:**

```python
class VoiceAgentService:  # Back to ~50 LOC!
    """Top-level orchestrator - only for true cross-domain workflows"""

    def __init__(self):
        self.core = CoreVoiceAgentService()
        self.operations = OperationsService()
        self.customization = CustomizationService()

    # Most methods: Simple domain delegation (1 line each)
    async def create_agent(self, config):
        return await self.core.create_agent(config)

    async def delete_agent(self, agent_id):
        return await self.core.delete_agent(agent_id)

    async def update_profile(self, agent_id, profile):
        return await self.customization.update_profile(agent_id, profile)

    async def setup_monitoring(self, agent_id):
        return await self.operations.setup_monitoring(agent_id)

    # Few methods: True cross-domain workflows
    async def create_production_ready_agent(self, config):
        """Only workflows that truly span multiple domains"""
        async with db.transaction():
            # Step 1: Create in core domain
            agent = await self.core.create_agent(config.base)

            # Step 2: Apply customizations
            await self.customization.apply_production_template(agent.id, config.template)

            # Step 3: Enable operations
            return await self.operations.make_production_ready(agent.id, config.ops)
```

**Domain-Specific Orchestrators:**

```python
# operations/service.py - Complex workflows within operations domain
class OperationsService:  # ~200 LOC - focused complexity
    """Orchestrator for production operations workflows"""

    def __init__(self):
        self.monitoring = MonitoringService()
        self.backup = BackupService()
        self.testing = TestingService()

    async def make_production_ready(self, agent_id, ops_config):
        """Complex workflow contained within operations domain"""
        # Multi-step production readiness workflow
        monitoring_result = await self.monitoring.setup_comprehensive_monitoring(
            agent_id, ops_config.monitoring
        )

        backup_result = await self.backup.schedule_production_backups(
            agent_id, ops_config.backup_schedule
        )

        test_results = await self.testing.run_production_test_suite(
            agent_id, ops_config.test_requirements
        )

        if not test_results.all_passed:
            await self._handle_production_test_failures(agent_id, test_results)
            raise ProductionReadinessError(test_results.failures)

        return ProductionReadyResult(
            agent_id, monitoring_result, backup_result, test_results
        )
```

## Key Benefits of Evolution Approach

1. **No Premature Optimization**: Teams can have 10+ services with simple delegation without restructuring
2. **Clear Breaking Points**: Restructure based on complexity, not arbitrary size limits
3. **Preserves Team Ownership**: Domain clusters align with team boundaries
4. **Maintains Thin Orchestrators**: Each level stays focused and understandable
5. **Natural Domain Boundaries**: Split along business domain lines, not technical convenience

## Evolution Anti-Patterns to Avoid

❌ **Restructuring Too Early**: Don't split when orchestrator is still pure delegation, even with 15+ methods

❌ **Splitting by Technical Layers**: Don't create `crud/`, `validation/`, `persistence/` - split by business domains

❌ **Creating Deep Hierarchies**: Avoid more than 2-3 levels of orchestration depth

❌ **Mixing Simple and Complex**: Don't let simple delegation methods live alongside complex workflows in the same orchestrator

## Multi-Tenant Service Pattern: Admin vs Regular Operations

**Key Principle:** Use a single service with optional `organization_id` parameter to support both tenant-scoped (regular users) and cross-tenant (admin users) operations without code duplication.

### The Pattern

```python
class PhoneService:
    async def list_phone_numbers(
        self,
        db: AsyncSession,
        organization_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        List phone numbers.

        Args:
            organization_id: If provided, filter to org's phones.
                           If None, return all phones (admin mode).
        """
        # Query database
        if organization_id is None:
            # Admin mode: return all phones
            stmt = select(PhoneNumber)
        else:
            # Tenant mode: filter to specific org
            stmt = select(PhoneNumber).where(
                PhoneNumber.organization_id == organization_id
            )

        result = await db.execute(stmt)
        return {"success": True, "phone_numbers": result.scalars().all()}
```

### Router Usage

**Regular Router (Tenant-Scoped):**

```python
@router.get("/phone-numbers")
async def list_phones(
    org_context: OrganizationContextDep,  # User's org from auth
    db: DatabaseDep,
):
    phone_service = PhoneService()
    return await phone_service.list_phone_numbers(
        db=db,
        organization_id=org_context.organization_id  # ← Always scoped to user's org
    )
```

**Admin Router (Cross-Tenant):**

```python
@router.get("/admin/retell/phone-numbers")
async def admin_list_phones(
    db: DatabaseDep,
    _: None = Depends(require_admin_api_key),  # Admin API key required
):
    phone_service = PhoneService()
    return await phone_service.list_phone_numbers(
        db=db,
        organization_id=None  # ← Admin mode: all orgs
    )
```

### Guidelines

**DO:**

- ✅ Use `Optional[str]` for organization_id parameter
- ✅ Default to `None` for clearest admin behavior
- ✅ Make organization_id the LAST parameter (after db session)
- ✅ Document both modes in docstring
- ✅ Keep same clean architecture: router → service → integration

**DON'T:**

- ❌ Create separate `admin_*` service classes (code duplication)
- ❌ Check admin permissions in service (belongs in router)
- ❌ Put organization_id as first parameter
- ❌ Have admin router bypass service layer to call integration directly

### Benefits

1. **No Code Duplication** - One service method handles both use cases
2. **Clear Intent** - `organization_id=None` explicitly signals admin mode
3. **Type-Safe** - `Optional[str]` provides compile-time safety
4. **Same Architecture** - Admin operations follow same router → service → integration pattern
5. **Easy Testing** - Test different scenarios by changing organization_id parameter

### Complete Example

See [Admin Operations Pattern Documentation](../docs/ADMIN_OPERATIONS_PATTERN.md) for comprehensive examples and testing strategies.

## Related Guides

- [Directory Organization](directory-organization.md) - How to organize these services in your file structure
- [API Design Patterns](api-design-patterns.md) - How routers interact with these service layers
- [Decision Frameworks](decision-frameworks.md) - Decision matrices for when to split or restructure services
- [Admin Operations Pattern](../docs/ADMIN_OPERATIONS_PATTERN.md) - Detailed multi-tenant service implementation guide
