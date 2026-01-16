# Tools Documentation

## Overview

Tools are the primary interface between the agent and the system's capabilities. Each tool encapsulates a specific action the agent can take.

## Tool Architecture

### Base Tool Structure

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseTool(ABC):
    """Base class for all agent tools"""
    
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters"""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate parameters against schema"""
        pass
```

## Current Tools (MVP)

### 1. SearchProductsTool

**Purpose**: Find products based on search criteria

**Parameters**:
- `query` (str): Search query
- `category` (str, optional): Product category filter
- `price_range` (tuple, optional): Min and max price
- `limit` (int): Maximum results to return

**Returns**: List of products matching criteria

**Example**:
```python
result = await tool.execute(
    query="running shoes",
    category="footwear",
    price_range=(50, 150),
    limit=5
)
```

### 2. GetProductDetailsTool

**Purpose**: Get detailed information about a specific product

**Parameters**:
- `product_id` (str): Shopify product ID
- `include_inventory` (bool): Include stock information

**Returns**: Complete product information

**Example**:
```python
details = await tool.execute(
    product_id="gid://shopify/Product/123456",
    include_inventory=True
)
```

### 3. CheckInventoryTool

**Purpose**: Check stock availability for products

**Parameters**:
- `product_id` (str): Product ID
- `variant_id` (str, optional): Specific variant
- `location_id` (str, optional): Store location

**Returns**: Inventory levels and availability

## Planned Tools (Future PRs)

### Cart Management Tools

#### AddToCartTool
- Add products to customer's cart
- Handle variant selection
- Quantity management

#### RemoveFromCartTool
- Remove items from cart
- Update quantities

#### GetCartSummaryTool
- Current cart contents
- Total price calculation
- Applied discounts

### Sizing Tools

#### GetSizeChartTool
- Retrieve size charts for products
- Brand-specific sizing

#### CompareSizesTool
- Compare sizes across brands
- Fit recommendations

#### SizeRecommendationTool
- Personalized size suggestions
- Based on previous purchases

### Recommendation Tools

#### GetRecommendationsTool
- Product suggestions based on browsing
- Complementary items

#### GetUpsellsTool
- Premium alternatives
- Bundle suggestions

#### GetCrossSellsTool
- Related products
- Frequently bought together

### Policy Tools

#### GetReturnPolicyTool
- Return policy details
- Product-specific policies

#### GetShippingInfoTool
- Shipping rates and times
- Delivery options

#### GetFAQTool
- Common questions
- Store policies

## Tool Registration

### Automatic Registration

Tools are automatically discovered and registered:

```python
# orchestration/tools/product_tools.py
from orchestration.tools.base import register_tool

@register_tool("search_products")
class SearchProductsTool(BaseTool):
    name = "search_products"
    description = "Search for products in the catalog"
    
    async def execute(self, **kwargs):
        # Implementation
        pass
```

### Manual Registration

For dynamic tools:

```python
from orchestration.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register(CustomTool())
```

## Tool Selection

The agent selects tools based on:

1. **Intent Recognition**: Understanding user's goal
2. **Tool Descriptions**: Matching capabilities
3. **Context**: Previous conversation state

### Selection Algorithm

```python
def select_tool(intent: str, context: Dict) -> BaseTool:
    # Score each tool based on relevance
    scores = {}
    for tool in registry.get_all():
        scores[tool] = calculate_relevance(
            tool.description,
            intent,
            context
        )
    
    # Return highest scoring tool
    return max(scores, key=scores.get)
```

## Error Handling

### Tool Execution Errors

```python
class ToolExecutionError(Exception):
    """Raised when tool execution fails"""
    
    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message

class ToolNotFoundError(Exception):
    """Raised when requested tool doesn't exist"""
    pass
```

### Retry Strategy

```python
async def execute_with_retry(tool: BaseTool, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await tool.execute(**kwargs)
        except ToolExecutionError as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

## Testing Tools

### Unit Testing

```python
# tests/unit/orchestration/test_product_tools.py
import pytest
from orchestration.tools.product_tools import SearchProductsTool

@pytest.mark.asyncio
async def test_search_products():
    tool = SearchProductsTool()
    
    # Mock Shopify client
    with mock.patch('shopify.client') as mock_client:
        mock_client.search.return_value = [...]
        
        result = await tool.execute(query="shoes")
        
        assert len(result) > 0
        assert all(p.type == "Product" for p in result)
```

### Integration Testing

```python
@pytest.mark.integration
async def test_tool_chain():
    # Test multiple tools working together
    search_tool = SearchProductsTool()
    detail_tool = GetProductDetailsTool()
    
    # Search for products
    products = await search_tool.execute(query="shirt")
    
    # Get details for first result
    details = await detail_tool.execute(
        product_id=products[0].id
    )
    
    assert details.id == products[0].id
```

## Best Practices

### 1. Single Responsibility
Each tool should do one thing well:
- ✅ `SearchProductsTool` - searches products
- ❌ `SearchAndAddToCartTool` - does two things

### 2. Idempotency
Tools should be safe to retry:
```python
# Good: Checking inventory is idempotent
await CheckInventoryTool().execute(product_id="123")

# Careful: Adding to cart might need deduplication
await AddToCartTool().execute(product_id="123")
```

### 3. Clear Parameters
Use descriptive parameter names:
```python
# Good
await tool.execute(
    product_id="123",
    include_variants=True
)

# Bad
await tool.execute(id="123", iv=True)
```

### 4. Comprehensive Logging
```python
async def execute(self, **kwargs):
    logger.info(f"Executing {self.name} with {kwargs}")
    try:
        result = await self._execute_internal(**kwargs)
        logger.info(f"{self.name} completed successfully")
        return result
    except Exception as e:
        logger.error(f"{self.name} failed: {e}")
        raise
```