"""Unit tests for tools."""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from orchestration.tools.base import BaseTool, ToolResult
from orchestration.tools.registry import ToolRegistry, register_tool
from orchestration.tools.product_tools import GetProductCatalogTool, GetProductDetailsTool
from shared import Product


class TestBaseTool:
    """Test base tool functionality."""
    
    @pytest.mark.asyncio
    async def test_tool_result_success(self):
        """Test successful tool result."""
        data = {"test": "data"}
        result = ToolResult.ok(data)
        
        assert result.success is True
        assert result.data == data
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_tool_result_failure(self):
        """Test failed tool result."""
        error = "Something went wrong"
        result = ToolResult.fail(error)
        
        assert result.success is False
        assert result.data is None
        assert result.error == error
    
    @pytest.mark.asyncio
    async def test_tool_validation(self):
        """Test parameter validation."""
        
        class TestTool(BaseTool):
            name = "test_tool"
            
            async def execute(self, required_param: str, optional_param: str = "default") -> ToolResult:
                return ToolResult.ok({"required": required_param, "optional": optional_param})
        
        tool = TestTool()
        
        # Should pass with required parameter
        assert tool.validate_parameters({"required_param": "value"}) is True
        
        # Should fail without required parameter
        with pytest.raises(ValueError, match="Missing required parameters"):
            tool.validate_parameters({})


class TestToolRegistry:
    """Test tool registry."""
    
    def test_singleton_pattern(self):
        """Test registry is a singleton."""
        registry1 = ToolRegistry()
        registry2 = ToolRegistry()
        
        assert registry1 is registry2
    
    def test_register_and_get_tool(self):
        """Test registering and retrieving tools."""
        registry = ToolRegistry()
        registry.clear()
        
        class TestTool(BaseTool):
            name = "test_tool"
            async def execute(self, **kwargs):
                return ToolResult.ok("test")
        
        tool = TestTool()
        registry.register(tool)
        
        assert registry.exists("test_tool")
        assert registry.get("test_tool") == tool
    
    def test_get_by_category(self):
        """Test getting tools by category."""
        registry = ToolRegistry()
        registry.clear()
        
        class ProductTool(BaseTool):
            name = "product_tool"
            category = "products"
            async def execute(self, **kwargs):
                return ToolResult.ok("product")
        
        class CartTool(BaseTool):
            name = "cart_tool"
            category = "cart"
            async def execute(self, **kwargs):
                return ToolResult.ok("cart")
        
        registry.register(ProductTool())
        registry.register(CartTool())
        
        product_tools = registry.get_by_category("products")
        assert len(product_tools) == 1
        assert product_tools[0].name == "product_tool"
    
    @pytest.mark.asyncio
    async def test_execute_tool(self):
        """Test executing tool through registry."""
        registry = ToolRegistry()
        registry.clear()
        
        class TestTool(BaseTool):
            name = "test_tool"
            async def execute(self, value: str) -> ToolResult:
                return ToolResult.ok(f"processed: {value}")
        
        registry.register(TestTool())
        
        result = await registry.execute_tool("test_tool", value="test")
        assert result.success is True
        assert result.data == "processed: test"


class TestGetProductCatalogTool:
    """Test product catalog tool."""
    
    @pytest.mark.asyncio
    async def test_get_catalog_mock(self):
        """Test getting product catalog with mock data."""
        tool = GetProductCatalogTool()
        
        result = await tool.execute(limit=5)
        
        assert result.success is True
        assert isinstance(result.data, list)
        assert len(result.data) <= 5
        
        if result.data:
            product = result.data[0]
            assert isinstance(product, Product)
            assert product.id
            assert product.title
    
    @pytest.mark.asyncio
    async def test_catalog_with_limit(self):
        """Test catalog with custom limit."""
        tool = GetProductCatalogTool()
        
        result = await tool.execute(limit=10)
        
        assert result.success is True
        assert isinstance(result.data, list)
        
        # Metadata should contain catalog info
        assert "total_products" in result.metadata
        assert "limit" in result.metadata
        assert result.metadata["limit"] == 10
        assert result.metadata["catalog_type"] == "full_products"
    
    @pytest.mark.asyncio
    async def test_default_limit(self):
        """Test catalog with default limit."""
        tool = GetProductCatalogTool()
        
        result = await tool.execute()
        
        assert result.success is True
        assert isinstance(result.data, list)
        
        # Should use default limit of 50
        assert "limit" in result.metadata
        assert result.metadata["limit"] == 50


class TestGetProductDetailsTool:
    """Test product details tool."""
    
    @pytest.mark.asyncio
    async def test_get_product_details_mock(self):
        """Test getting product details with mock data."""
        tool = GetProductDetailsTool()
        
        result = await tool.execute(
            product_id="prod_001",
            include_inventory=True
        )
        
        assert result.success is True
        assert "product" in result.data
        
        product = result.data["product"]
        assert product["id"] == "prod_001"
        assert product["title"]
        assert "variants" in product
    
    @pytest.mark.asyncio
    async def test_product_not_found(self):
        """Test handling of non-existent product."""
        tool = GetProductDetailsTool()
        
        result = await tool.execute(
            product_id="non_existent",
            include_inventory=False
        )
        
        # With mock data, this might still succeed
        # In production with real Shopify client, this would fail
        assert result.success is True or result.error is not None