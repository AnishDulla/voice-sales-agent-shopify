# ReactFlow Patterns & Best Practices for Stello

## Overview

This guide documents patterns for building type-safe, maintainable workflow builders with ReactFlow. It focuses on **actual patterns used in Stello's workflow builder** rather than exhaustive ReactFlow documentation.

## Golden Rules

1. **Node Data Discriminated Unions**: Use discriminated unions for node data variants (e.g., trigger selecting vs configured state)
2. **Handle IDs**: Make handle IDs globally unique by including node ID (e.g., `${nodeId}-yes`, `${nodeId}-no`)
3. **State Management**: Use refs in hooks to avoid closure issues with async state updates
4. **Transform Separation**: Keep backend format (`WorkflowNodeConfig`) separate from ReactFlow format (`Node`)
5. **Layout Responsibility**: Use layout algorithms for positioning; don't manually set positions then apply layout
6. **Type Guards Over Assertions**: Use type guard functions (ReactFlow's official pattern) instead of type assertions for node type narrowing

## TypeScript Type Safety Pattern (CRITICAL)

Following [ReactFlow's official TypeScript guide](https://reactflow.dev/learn/advanced-use/typescript), use type guards for full type safety without assertions.

### Step 1: Define Typed Nodes with Discriminated Unions

Use Node intersection pattern to avoid generic constraints:

```typescript
// Define typed nodes (discriminated by node.type)
export type TriggerNode = Node & { type: 'trigger'; data: TriggerNodeData };
export type CallNode = Node & { type: 'call_contact'; data: CallUserNodeData };
export type DelayNode = Node & { type: 'delay'; data: WaitNodeData };
export type ConditionNode = Node & { type: 'condition'; data: IfConditionNodeData };

// Union type (CustomNodeType is ReactFlow's naming convention)
export type CustomNodeType =
  | TriggerNode
  | CallNode
  | DelayNode
  | ConditionNode;
```

### Step 2: Create Type Guard Functions

Type predicates enable TypeScript to narrow union types automatically:

```typescript
export function isTriggerNode(node: CustomNodeType | Node): node is TriggerNode {
  return node.type === 'trigger';
}

export function isCallNode(node: CustomNodeType | Node): node is CallNode {
  return node.type === 'call_contact';
}

export function isDelayNode(node: CustomNodeType | Node): node is DelayNode {
  return node.type === 'delay';
}

export function isConditionNode(node: CustomNodeType | Node): node is ConditionNode {
  return node.type === 'condition';
}
```

### Step 3: Use Type Guards for Type-Safe Narrowing

No assertions needed - type guards automatically narrow:

```typescript
function transformReactFlowNodeToBackend(node: CustomNodeType | Node): WorkflowNodeConfig | null {
  if (isTriggerNode(node)) {
    const { data } = node; // TypeScript knows node is TriggerNode
    return {
      id: node.id,
      config: {
        type: 'trigger',
        name: data.name,        // ✅ Type-safe
        triggerType: data.triggerType,
        subtitle: data.subtitle,
      },
    };
  }

  if (isDelayNode(node)) {
    const { data } = node; // TypeScript knows node is DelayNode
    // Full type safety on all data.config properties
    const config: WaitNodeConfig = {
      type: 'wait',
      name: data.name,
      mode: data.config.mode ?? 'duration', // ✅ Proper default handling
      duration: data.config.duration,
      unit: data.config.unit,
      target_time: data.config.target_time,
      timezone: data.config.timezone,
    };
    return { id: node.id, config };
  }

  if (isConditionNode(node)) {
    const { data } = node; // TypeScript knows node is ConditionNode
    // No assertion needed for combinator - type is already 'and' | 'or'
    const config: ConditionNodeConfig = {
      type: 'condition',
      name: data.name,
      conditions: data.config.conditions,
      combinator: data.config.combinator, // ✅ Type-safe, no assertion
    };
    return { id: node.id, config };
  }

  return null;
}
```

**Benefits of This Pattern:**
- ✅ **Zero type assertions** - No `as` keyword needed for data access
- ✅ **Full type safety** - TypeScript catches access errors at compile time
- ✅ **Official ReactFlow pattern** - Recommended in ReactFlow's TypeScript guide
- ✅ **Eliminates code smell** - Fixes type assertion + fallback contradictions
- ✅ **Reusable guards** - Same guards work for filtering, mapping, and narrowing

## Why ReactFlow Needs Special Guidance

ReactFlow has specific type constraints that require documented patterns:

- Generic constraint: `Node<T extends Record<string, unknown>>`
- ReactFlow hooks return generic `Node<Record<string, unknown>>` types, not custom types
- This means we can't use discriminated unions at the Node level for ReactFlow APIs
- Function properties in node data require explicit handling due to type constraints

## Type Safety with Discriminated Unions

Use discriminator fields to create type-safe unions. This is used in Stello for node data states.

### Example: Trigger Node States

```typescript
// State 1: User selecting a trigger type
export interface TriggerNodeDataSelecting {
  state: 'selecting';  // Discriminator
  onSelectTrigger: (triggerType: string) => void;
  onAddAction?: (...) => void;
}

// State 2: Trigger configured
export interface TriggerNodeDataConfigured {
  state: 'configured';  // Discriminator
  label: string;
  triggerType: string;
  onAddAction?: (...) => void;
}

// Discriminated union
export type TriggerNodeData = TriggerNodeDataSelecting | TriggerNodeDataConfigured;

// Type guards
export function isTriggerSelecting(data: TriggerNodeData): data is TriggerNodeDataSelecting {
  return data.state === 'selecting';
}

export function isTriggerConfigured(data: TriggerNodeData): data is TriggerNodeDataConfigured {
  return data.state === 'configured';
}
```

### Example: Action Point Variants

Stello uses discriminated unions for action points (linear vs branching):

```typescript
// Linear action point (from call/delay nodes)
export interface LinearActionPointNodeData {
  kind: 'linear';
  onAddAction: (actionType: string) => void;
  sourceNodeId: string;
}

// Branching action point (from conditional nodes)
export interface BranchingActionPointNodeData {
  kind: 'branching';
  branchType: 'yes' | 'no';  // Required
  onAddAction: (actionType: string, branchType: 'yes' | 'no') => void;
  sourceNodeId: string;
}

export type ActionPointNodeData = LinearActionPointNodeData | BranchingActionPointNodeData;
```

**Type guards ensure correct usage:**

```typescript
export function isLinearActionPoint(
  data: ActionPointNodeData,
): data is LinearActionPointNodeData {
  return data.kind === 'linear';
}

export function isBranchingActionPoint(
  data: ActionPointNodeData,
): data is BranchingActionPointNodeData {
  return data.kind === 'branching';
}
```

## Custom Node Component Patterns

### Basic Structure

```typescript
import { NodeProps } from '@xyflow/react';
import type { WaitNodeData } from '@/features/workflows/types';

export function WaitNode({ data, selected }: NodeProps<WaitNodeData>) {
  return (
    <div className={selected ? 'border-blue-500' : 'border-gray-300'}>
      <div className="font-semibold">{data.label}</div>
      <div className="text-sm text-gray-600">
        {data.config.duration} {data.config.unit}
      </div>
    </div>
  );
}
```

### Multi-Output Nodes (Branching)

For nodes with multiple output branches (e.g., conditional nodes):

```typescript
import { Handle, Position } from '@xyflow/react';
import type { IfConditionNodeData } from '@/features/workflows/types';

export function IfConditionNode({ data, selected }: NodeProps<IfConditionNodeData>) {
  return (
    <div>
      <div>{data.label}</div>
      {/* Output handles for branching */}
      <Handle
        type="source"
        position={Position.Right}
        id={`${id}-yes`}  // Globally unique
      />
      <Handle
        type="source"
        position={Position.Right}
        id={`${id}-no`}  // Globally unique
      />
    </div>
  );
}
```

## State Management Patterns

### The useWorkflowGraph Hook

Stello centralizes all workflow graph operations in `useWorkflowGraph`:

```typescript
const {
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  updateNode,
  getWorkflowDefinition,
} = useWorkflowGraph();
```

### Avoiding Stale Closures

Use refs to maintain current state for async operations:

```typescript
const nodesRef = useRef<Node[]>([]);
const edgesRef = useRef<WorkflowEdge[]>([]);

useEffect(() => {
  nodesRef.current = nodes;  // Keep in sync
}, [nodes]);

useEffect(() => {
  edgesRef.current = edges;  // Keep in sync
}, [edges]);

// Later, use refs for layout operations:
const applyLayout = useCallback(
  async (nodesToLayout: Node[], edgesToLayout: WorkflowEdge[]) => {
    const layoutedNodes = await getLayoutedElements(nodesToLayout, edgesToLayout);
    setNodes(layoutedNodes);  // Works correctly with fresh state
  },
  [setNodes]
);
```

## Transform Utilities

### Backend ↔ ReactFlow Format

Transformations maintain clear separation between formats:

**Backend Format (`WorkflowNodeConfig`):**
```typescript
{
  id: "node-1",
  type: "wait",
  config: {
    type: "wait" as const,
    label: "Wait 5 days",
    duration: 5,
    unit: "days"
  }
}
```

**ReactFlow Format (`Node`):**
```typescript
{
  id: "node-1",
  type: "delay",
  position: { x: 100, y: 200 },
  data: {
    label: "Wait 5 days",
    config: {
      duration: 5,
      unit: "days"
    }
  }
}
```

### Pattern: Two-Way Transformations

```typescript
// Backend → ReactFlow
export function transformBackendToReactFlow(
  definition: WorkflowDefinition
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];

  if (definition.nodes && definition.nodes.length > 0) {
    definition.nodes.forEach((backendNode) => {
      const reactFlowNode = transformBackendNodeToReactFlow(backendNode);
      if (reactFlowNode) {
        nodes.push(reactFlowNode);
      }
    });
  }

  // ... handle edges and triggers ...

  return { nodes, edges };
}

// ReactFlow → Backend
export function transformReactFlowToBackend(
  nodes: Node[],
  edges: Edge[],
  startNodeId: string
): WorkflowDefinition {
  const backendNodes = nodes
    .filter((node) => !nodesToFilterOut.has(node.id))
    .map((node) => transformReactFlowNodeToBackend(node))
    .filter((node): node is WorkflowNodeConfig => node !== null);

  return {
    start_node: startNodeId,
    triggers,
    nodes: backendNodes,
    edges: backendEdges,
  };
}
```

## Layout & Positioning

### Using ELK.js (Preferred)

Stello uses `elkjs` for deterministic, aesthetic layout:

```typescript
import { getLayoutedElements } from '@/features/workflows/builder/utils/layout';

const layoutedNodes = await getLayoutedElements(nodes, edges);
// Returns nodes with computed positions
```

### Deterministic Positioning Fallback

For seed values or consistent positions without layout:

```typescript
function getNodePosition(nodeId: string): { x: number; y: number } {
  // Hash-based positioning ensures same ID → same position
  let hash = 0;
  for (let i = 0; i < nodeId.length; i++) {
    hash = (hash << 5) - hash + nodeId.charCodeAt(i);
  }

  const x = 100 + Math.abs(hash % 400) * 50;
  const y = 100 + Math.abs(Math.floor(hash / 400) % 300) * 50;
  return { x, y };
}
```

## Testing ReactFlow Components

### Testing Transform Functions

Transform functions are pure and should be tested independently:

```typescript
describe('transformBackendToReactFlow', () => {
  it('converts wait node with correct config', () => {
    const backendNode: WorkflowNodeConfig = {
      id: 'node-1',
      type: 'wait',
      config: {
        type: 'wait',
        label: 'Wait',
        duration: 5,
        unit: 'days'
      }
    };

    const result = transformBackendToReactFlow({
      start_node: 'node-1',
      triggers: [],
      nodes: [backendNode],
      edges: []
    });

    const node = result.nodes[0];
    expect(node.type).toBe('delay');
    expect(node.data.config.duration).toBe(5);
  });
});
```

### Testing Node Components

Use MSW + React Testing Library:

```typescript
import { render, screen } from '@testing-library/react';
import { WaitNode } from './WaitNode';

it('displays wait duration', () => {
  const data: WaitNodeData = {
    label: 'Wait 5 days',
    config: { duration: 5, unit: 'days' }
  };

  render(
    <WaitNode data={data} selected={false} />
  );

  expect(screen.getByText('5 days')).toBeInTheDocument();
});
```

## Common Pitfalls

### 1. Using `as any` for Type Issues

**❌ Bad:**
```typescript
const config = backendNode.config as any;  // Loses all type info
```

**✅ Good:**
```typescript
// Cast to specific expected type
const config = backendNode.config as { label: string; duration: number };
```

### 2. Stale Closure in Callbacks

**❌ Bad:**
```typescript
const addNode = useCallback(() => {
  // `nodes` is stale - closure captured old state
  setNodes([...nodes, newNode]);
}, [nodes]); // Re-creates on every render
```

**✅ Good:**
```typescript
const nodesRef = useRef<Node[]>([]);

useEffect(() => {
  nodesRef.current = nodes;
}, [nodes]);

const addNode = useCallback(() => {
  // Fresh state from ref
  const current = nodesRef.current;
  setNodes([...current, newNode]);
}, []); // Stable callback
```

### 3. Non-Unique Handle IDs

**❌ Bad:**
```typescript
<Handle id="yes" />  // Only one node can have this
```

**✅ Good:**
```typescript
<Handle id={`${nodeId}-yes`} />  // Globally unique
```

### 4. Type Assertion + Fallback Contradiction (Code Smell)

**❌ Bad:**
```typescript
// This pattern is contradictory:
// Type assertion says "this IS 'and' | 'or'"
// Fallback says "but it might not be, use 'and' as default"
combinator: (nodeConfig?.combinator as 'and' | 'or') || 'and'
```

**Why it's a code smell:**
- Type assertion claims type safety but then fallback contradicts it
- Invalid values like `'or '` (with space) pass the assertion and bypass the fallback
- Masks the real issue: improper type narrowing

**✅ Good (use type guards instead):**
```typescript
// Define the node as properly typed
export type ConditionNode = Node & { type: 'condition'; data: IfConditionNodeData };

// Create type guard
export function isConditionNode(node: CustomNodeType | Node): node is ConditionNode {
  return node.type === 'condition';
}

// Use in function
if (isConditionNode(node)) {
  const { data } = node; // TypeScript knows data.config.combinator is already 'and' | 'or'
  const config: ConditionNodeConfig = {
    type: 'condition',
    name: data.name,
    conditions: data.config.conditions,
    combinator: data.config.combinator, // ✅ No assertion needed
  };
  return { id: node.id, config };
}
```

The type guard pattern is cleaner, more truthful about what we know, and follows ReactFlow's official guidance.

## Decision Frameworks

### Use Discriminated Unions When:
- Multiple variants of data with different required properties
- Need compile-time enforcement that properties match variant
- Examples: trigger states, action point kinds

### Use Type Guards When:
- Narrowing CustomNodeType to specific node types (ALWAYS - ReactFlow's official pattern)
- Filtering/mapping arrays of nodes where type safety matters
- Distinguishing between discriminated union variants
- Example: `if (isTriggerNode(node)) { const { data } = node; }` ← Type-safe narrowing

## Quick Reference

**Files to Review:**
- Type definitions: `src/features/workflows/types/index.ts`
- Custom nodes: `src/features/workflows/builder/components/nodes/`
- Hook: `src/features/workflows/builder/hooks/useWorkflowGraph.ts`
- Transforms: `src/features/workflows/builder/utils/transforms.ts`
- Layout: `src/features/workflows/builder/utils/layout.ts`

**Key Patterns:**
1. **Type guards** for node type narrowing (ReactFlow's official pattern) - ALWAYS use these
2. Discriminated unions for node data variants (trigger states, action point kinds)
3. Global handle IDs (include node ID)
4. Refs for avoiding stale closures
5. Clean separation between backend and ReactFlow formats
6. Use layout algorithms, not manual positioning
