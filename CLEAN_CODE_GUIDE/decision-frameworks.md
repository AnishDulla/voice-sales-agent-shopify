# Decision Frameworks

This guide consolidates all decision-making frameworks, matrices, and checklists to help you make consistent architectural choices.

## Service Design Decisions

### Do I Even Need an Orchestrator?

**This is the FIRST question to ask when designing services.**

**Default Answer: NO** - Start without an orchestrator. Only add one when you have actual coordination needs.

**❌ Skip Orchestrator (Router → Direct Service Calls) When:**

- ✅ **Single specialized service** handles the entire domain
- ✅ **No cross-service coordination** needed
- ✅ **Greenfield project** with no backward compatibility concerns
- ✅ **Simple delegation** - orchestrator would just forward calls 1:1

**Example - No Orchestrator Needed:**

```python
# router.py - Calls service directly
from app.features.templates.template_service import get_template_service

@router.post("/templates")
async def create_template(request: CreateTemplateRequest, db: DatabaseDep):
    """Router calls specialized service directly - no orchestrator needed"""
    service = get_template_service()
    return await service.create_template(request, db)
```

**✅ Add Orchestrator When:**

- ✅ **Multiple specialized services** need coordination (CSV service needs CRUD service)
- ✅ **Cross-service workflows** exist (lifecycle service fetches from CRUD, then updates)
- ✅ **Backward compatibility** matters (50+ existing imports you don't want to change)
- ✅ **Actual coordination logic** beyond simple delegation (conditional service calls, transactions)

**Example - Orchestrator Justified:**

```python
# service.py - Thin orchestrator with real coordination
class ContactService:
    def __init__(self):
        self.crud = ContactCRUDService()
        self.csv = ContactCSVService(self.crud)  # ← CSV depends on CRUD
        self.lifecycle = ContactLifecycleService()

    async def update_contact_from_call_analysis(self, contact_id, org_id, ...):
        """Real coordination: fetch from CRUD, update via Lifecycle"""
        contact = await self.crud.get_contact(contact_id, org_id, db)
        if not contact:
            return None
        return await self.lifecycle.update_from_analysis(contact, ...)  # ← Coordination
```

**Warning Signs You Don't Need an Orchestrator:**

```python
# 🚨 RED FLAG: Orchestrator adds ZERO value
class UserService:
    def __init__(self):
        self.crud = UserCRUDService()

    # Every method is 1-line delegation with no coordination
    async def create_user(self, data):
        return await self.crud.create_user(data)  # ← Why does this exist?

    async def get_user(self, user_id):
        return await self.crud.get_user(user_id)  # ← Just use crud directly!

    async def delete_user(self, user_id):
        return await self.crud.delete_user(user_id)  # ← Unnecessary layer
```

**Golden Rule**: If your orchestrator is 100% simple delegation with no coordination, you probably don't need it. Call specialized services directly from routers.

### When to Split Services

**Service >500 LOC or >8 public operations**

- Service has grown beyond maintainability limits
- Multiple business domains in one service
- Unrelated data models or capabilities

**When NOT to Split:**

- Service <400 LOC and <7 operations
- Splitting by technical layers (database, business, orchestration)
- Split services would constantly call each other

### When to Move Models to Features

**Move to Feature `models.py` When:**

- Model used by 1-2 features only
- Feature-specific configuration (RetellConfiguration, AppointmentSettings)
- Clear domain boundary (could be owned by single team)
- Model isn't a foreign key target for many tables

**Keep in Global `models/` When:**

- Used by 3+ features (User, Organization)
- Core domain entities that define the business
- Frequent foreign key target (referenced by many tables)
- Authentication/authorization related models

### Service Architecture Evolution

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

### Service Instantiation Pattern Selection

**Choose Stateless Factory Pattern When:**

- ✅ **Small service** (<200 LOC)
- ✅ **Few methods** (1-4 public operations)
- ✅ **Methods are independent** - Each method works in isolation
- ✅ **Simple operations** - No complex state management
- ✅ **Utility service** - Helper functions with occasional database access

**Example Services Using Factory Pattern:**
- `TemplateService` - 3 methods, simple CRUD
- `ValidationService` - 2 helper methods
- `NotificationService` - Send notifications, minimal state

**Choose Stateful DI Pattern When:**

- ✅ **Larger service** (200-500 LOC)
- ✅ **Many methods** (5-8+ public operations)
- ✅ **All methods need database access** - Consistent session usage
- ✅ **CRUD pattern** - Create, Read, Update, Delete operations
- ✅ **Complex orchestration** - Methods call each other or coordinate

**Example Services Using DI Pattern:**
- `WorkflowCRUDService` - 8 methods, all need session
- `ContactCRUDService` - 7 methods, transaction management
- `PhoneNumberService` - 6 methods, heavy orchestration

**Decision Matrix:**

| Criteria | Stateless Factory | Stateful DI |
|----------|------------------|-------------|
| **Service Size** | <200 LOC | 200-500 LOC |
| **Method Count** | 1-4 methods | 5-8+ methods |
| **Session Usage** | <50% of methods | >80% of methods |
| **Pattern Type** | Utility, helper | CRUD, orchestrator |
| **Scalability** | Low (parameter duplication) | High (clean signatures) |
| **Setup Complexity** | Minimal | Moderate (need FastAPI DI knowledge) |
| **Testing** | Direct instantiation | Constructor injection |
| **Real-World Fit** | Simple operations | Complex multi-operation services |

**Quick Decision Flow:**

1. **Count public methods** - How many?
   - 1-4 → Consider factory pattern
   - 5-8+ → Consider DI pattern

2. **Check session usage** - What % of methods need database access?
   - <50% → Factory pattern (session as parameter)
   - >80% → DI pattern (session in __init__)

3. **Assess complexity** - Can your team maintain parameter duplication?
   - Yes → Factory pattern is fine
   - No → Move to DI pattern

**Migration Signal:**

If your service exceeds 4 methods and more than 50% of methods take a `db: AsyncSession` parameter, it's time to migrate to the stateful DI pattern. See [Service Instantiation Patterns](../service-architecture.md#service-instantiation--session-management-patterns) for migration guide.

## API Design Decisions

### Operation Type Decision Matrix

| Question                      | Simple CRUD     | Business Intent      | Atomic Multi-Step          | Complex Workflow           |
| ----------------------------- | --------------- | -------------------- | -------------------------- | -------------------------- |
| **Number of operations?**     | 1               | 2-4                  | 2-5                        | 5+                         |
| **External APIs involved?**   | Maybe 1         | 1-2                  | Multiple                   | Multiple                   |
| **Transaction requirements?** | Single DB       | None/Simple          | All-or-nothing             | Complex boundaries         |
| **Rollback complexity?**      | Simple          | Compensation         | Full compensation          | State machines             |
| **Service pattern?**          | Thin delegation | Orchestration method | Transaction + compensation | Dedicated workflow service |

### Frontend vs Backend Orchestration Decision Framework

**Choose Frontend Orchestration When:**

- ✅ **Simple workflows**: 2-4 API calls with clear sequence
- ✅ **User-facing operations**: Users benefit from progress feedback
- ✅ **Partial failure scenarios**: Can retry individual steps or continue with partial success
- ✅ **Frequent UX changes**: Workflow presentation changes often
- ✅ **Different team ownership**: APIs are owned by different teams
- ✅ **No complex business rules**: Simple sequence without conditional logic

**Choose Backend Orchestration When:**

- ✅ **Complex transactions**: Operations must be atomic (all succeed or all fail)
- ✅ **Security-sensitive**: Operations should not be exposed to client manipulation
- ✅ **Background processing**: Long-running or scheduled operations
- ✅ **Complex business rules**: Conditional logic based on intermediate results
- ✅ **High-performance requirements**: Minimize client-server round trips
- ✅ **Stateful workflows**: Operations depend on previous state changes

**Decision Questions:**

1. **Atomicity**: Do operations need database transaction guarantees?
2. **Security**: Should clients control the workflow sequence?
3. **Complexity**: Are there conditional business rules between steps?
4. **Performance**: Are round-trip costs prohibitive?

**If you answer "No" to most questions → Use frontend orchestration**
**If you answer "Yes" to multiple questions → Use backend orchestration**

## External API Integration Decisions

### External API Integration Decision Framework

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

## Integration Pattern Decisions

### When to Use Thin Wrappers vs Ports Pattern

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

### Functions vs Classes Decision Framework

**Use Standalone Functions When:**

1. **Pure Data Access/Queries** - No state, just database queries

   ```python
   async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
       # Simple query, no dependencies
   ```

2. **Stateless Utilities** - Pure functions with no dependencies

   ```python
   def format_phone_number(phone: str) -> str:
       # No state, no external dependencies
   ```

3. **Simple Operations** - Single responsibility, no coordination needed
   ```python
   async def send_notification(user_id: str, message: str) -> bool:
       # One thing, does it well
   ```

**Use Classes When:**

1. **Multiple Dependencies** - Need to coordinate several services

   ```python
   class AgentSetupService:
       def __init__(self):
           self.conversation_flows = get_conversation_flow_service()
           self.voice_agents = get_voice_agent_service()
           # Multiple dependencies to coordinate
   ```

2. **Stateful Operations** - Need to track state across method calls

   ```python
   class PaymentProcessor:
       def __init__(self):
           self.transaction_log = []
           # Maintains state
   ```

3. **Complex Workflows** - Multi-step processes with error handling/compensation

   ```python
   class OutboundAgentService:
       # Creates flow -> Creates agent -> Saves config
       # Needs compensation if any step fails
   ```

4. **Related Operations** - Grouped functionality that shares context
   ```python
   class CalendarService:
       def create_appointment(self): pass
       def update_appointment(self): pass
       def delete_appointment(self): pass
       # All work with same domain
   ```

## Implementation Pattern Selection

### Pattern 1: Simple CRUD (no compensation needed)

```python
async def get_agent_details(agent_id: str) -> AgentResponse:
    """Read-only operation - simple error handling"""
    try:
        agent = await self.retell_client.get_agent(agent_id)
        return AgentResponse(success=True, agent=agent)
    except ClientError as e:
        return AgentResponse(success=False, error="Agent not found")
    except Exception as e:
        return AgentResponse(success=False, error="Service unavailable")
```

### Pattern 2: Business Intent (compensation + orchestration)

```python
async def complete_agent_setup(self, request: SetupRequest) -> SetupResponse:
    """Multi-step with compensation - full pattern"""
    return await self._execute_with_compensation(
        steps=[
            ("flow", lambda: self.create_conversation_flow(request.flow_config)),
            ("agent", lambda: self.create_agent(request.agent_config)),
            ("phone", lambda: self.assign_phone_number(request.phone_config)),
        ],
        cleanup_func=self._cleanup_setup_resources
    )
```

### Pattern 3: Atomic Multi-Step (transaction boundaries)

```python
async def migrate_agent_atomically(self, agent_id: str, new_config: dict) -> MigrationResponse:
    """Atomic operation with external+internal consistency"""
    # External operations first (can't rollback)
    external_resources = await self._create_external_resources(new_config)

    try:
        # Database transaction
        async with db.begin():
            await self._update_local_configuration(agent_id, external_resources)
            await self._cleanup_old_external_resources(agent_id)
            return MigrationResponse(success=True)
    except Exception as e:
        # Compensate external resources
        await self._cleanup_external_resources(external_resources)
        return MigrationResponse(success=False, error=str(e))
```

## Nested vs Top-Level Orchestrator Decisions

**✅ Keep Nested Orchestrators When:**

- Each subdomain has 3-8 independent operations
- Different teams own different subdomains
- Subdomains rarely interact
- Each orchestrator stays <500 LOC

```python
# Independent operations - keep nested
templates/service.py      # Template CRUD + customization
voice_agents/service.py   # Agent creation + management
conversation_flow/service.py # Flow creation + validation
```

**⚠️ Consider Top-Level Orchestrator When:**

- Complex workflows span multiple subdomains
- Shared transactions across subdomains
- Any nested orchestrator exceeds 500 LOC

```python
# Cross-domain workflow requiring coordination
class RetellService:
    def __init__(self):
        self.templates = TemplateService()
        self.agents = VoiceAgentService()
        self.flows = ConversationFlowService()

    async def create_complete_voice_assistant(self, config):
        # True cross-domain workflow
        async with db.transaction():
            template = await self.templates.create_template(config.template_data)
            flow = await self.flows.create_flow(template)
            agent = await self.agents.create_agent(flow, config.voice_settings)
            return CompleteAssistant(template, flow, agent)
```

## Red Flags Checklist

**🚨 Immediate Action Required:**

- Services exceeding 500 LOC or 8 operations
- All models in global directory with >10 model files
- Integrations importing from features/ (creates cycles)
- Business logic in integration layers
- Using ports/adapters pattern with single vendors (premature abstraction)
- Service-to-service method calls
- Heavy business logic in orchestration methods
- Integration methods >20 lines (probably doing business logic)

## Quick Decision Checklist

### For New Services:

1. ✅ Does this use existing service layers?
2. ✅ Does this follow current API patterns?
3. ✅ Am I creating duplicate functionality?
4. ✅ Will this work with the current dev setup?
5. ✅ Is this consistent with neighboring code?

### For External API Integration:

1. ✅ Does this create expensive external resources? → Implement compensation
2. ✅ Are multiple external APIs involved? → Track resources, implement cleanup
3. ✅ Is this operation retryable? → Implement idempotency checks
4. ✅ Must the system stay consistent? → Use compensation patterns

### For API Design:

1. ✅ Can this endpoint be used independently? → Good atomic API
2. ✅ Does this endpoint only coordinate other APIs? → Consider frontend orchestration
3. ✅ Are there complex business rules between steps? → Backend orchestration
4. ✅ Do users need progress feedback? → Frontend orchestration

## Decision Framework Summary

**Start with Frontend Orchestration by Default for User-Facing Workflows**

Ask these questions to validate:

1. **Atomicity**: Do operations need database transaction guarantees?
2. **Security**: Should clients control the workflow sequence?
3. **Complexity**: Are there conditional business rules between steps?
4. **Performance**: Are round-trip costs prohibitive?

**For External API Integration, Always Ask:**

1. **Does this create expensive external resources?** → Implement compensation
2. **Are multiple external APIs involved?** → Track resources, implement cleanup
3. **Is this operation retryable?** → Implement idempotency checks
4. **Must the system stay consistent?** → Use compensation patterns

**Golden Rules:**

- Don't create backend orchestration layers just because you can. Create them because you must.
- If it creates external resources that cost money or quota, implement compensation.
- Each endpoint should be independently useful - avoid orchestration APIs that couple domains.

## Related Guides

- [Service Architecture](service-architecture.md) - Implementation details for service design decisions
- [API Design Patterns](api-design-patterns.md) - How to implement the orchestration patterns you choose
- [Integration Patterns](integration-patterns.md) - Implementation details for external API integration decisions
- [Anti-Patterns](anti-patterns.md) - What happens when you make the wrong choices
