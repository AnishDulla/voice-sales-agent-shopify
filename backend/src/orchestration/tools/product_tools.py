"""Product-related tools for the agent."""

from typing import List, Optional, Dict, Any

from orchestration.tools.base import BaseTool, ToolContext
from orchestration.tools.registry import register_tool
from shared import (
    ToolResult,
    Product
)
from domains.shopify.client import ShopifyClient
from domains.shopify.products import ProductService


@register_tool(name="get_product_catalog", category="products", description="Get the full product catalog for intelligent filtering")
class GetProductCatalogTool(BaseTool):
    """Tool for getting the full product catalog - let the LLM do the intelligent filtering."""
    
    name = "get_product_catalog"
    description = "Get all products in the catalog with full details - the LLM will intelligently filter based on user requests"
    category = "products"
    
    def __init__(self, shopify_client: Optional[ShopifyClient] = None):
        super().__init__()
        self.shopify_client = shopify_client
        self._product_service = None
    
    @property
    def product_service(self) -> ProductService:
        """Lazy load product service."""
        if not self._product_service and self.shopify_client:
            self._product_service = ProductService(self.shopify_client)
        return self._product_service
    
    async def execute(
        self,
        limit: int = 50
    ) -> ToolResult[List[Product]]:
        """
        Get the complete product catalog for intelligent LLM filtering.
        
        Args:
            limit: Maximum number of products to return (default 50)
        
        Returns:
            List of all products with full details for LLM to reason over
        """
        try:
            if not self.product_service:
                return ToolResult.fail("Shopify client not configured")
            
            # Get all products - let the LLM do the smart filtering
            products = await self.product_service.get_all_products(limit=limit)
            
            self.log_event(
                "fetched_product_catalog",
                count=len(products),
                limit=limit
            )
            
            return ToolResult.ok(
                data=products,
                metadata={
                    "total_products": len(products),
                    "limit": limit,
                    "catalog_type": "full_products"
                }
            )
            
        except Exception as e:
            self.log_error(e, "get_product_catalog_failed", limit=limit)
            return ToolResult.fail(f"Failed to get product catalog: {str(e)}")
    


@register_tool(name="get_product_details", category="products", description="Get detailed information about a product")
class GetProductDetailsTool(BaseTool):
    """Tool for getting product details."""
    
    name = "get_product_details"
    description = "Get complete details about a specific product including variants and inventory"
    category = "products"
    
    def __init__(self, shopify_client: Optional[ShopifyClient] = None):
        super().__init__()
        self.shopify_client = shopify_client
        self._product_service = None
    
    @property
    def product_service(self) -> ProductService:
        """Lazy load product service."""
        if not self._product_service and self.shopify_client:
            self._product_service = ProductService(self.shopify_client)
        return self._product_service
    
    async def execute(
        self,
        product_id: str,
        include_inventory: bool = True,
        include_related: bool = False
    ) -> ToolResult[Dict[str, Any]]:
        """
        Get detailed product information.
        
        Args:
            product_id: Product ID
            include_inventory: Include inventory levels
            include_related: Include related products
        
        Returns:
            Product details with optional inventory and related products
        """
        try:
            if not self.product_service:
                return ToolResult.fail("Shopify client not configured")
            
            product = await self.product_service.get_product_details(
                product_id=product_id,
                include_inventory=include_inventory
            )
            
            if not product:
                return ToolResult.fail(f"Product {product_id} not found")
            
            result = {
                "product": product.dict(),
                "variants_count": len(product.variants),
                "in_stock": product.available
            }
            
            if include_related:
                related = await self.product_service.get_related_products(
                    product=product,
                    limit=5
                )
                result["related_products"] = [p.dict() for p in related]
            
            return ToolResult.ok(
                data=result,
                metadata={"product_id": product_id}
            )
            
        except Exception as e:
            self.log_error(e, "get_product_details_failed", product_id=product_id)
            return ToolResult.fail(f"Failed to get product details: {str(e)}")
    


@register_tool(name="check_inventory", category="products", description="Check product inventory availability")
class CheckInventoryTool(BaseTool):
    """Tool for checking inventory."""
    
    name = "check_inventory"
    description = "Check if a product or specific variant is in stock"
    category = "products"
    
    def __init__(self, shopify_client: Optional[ShopifyClient] = None):
        super().__init__()
        self.shopify_client = shopify_client
        self._product_service = None
    
    @property
    def product_service(self) -> ProductService:
        """Lazy load product service."""
        if not self._product_service and self.shopify_client:
            self._product_service = ProductService(self.shopify_client)
        return self._product_service
    
    async def execute(
        self,
        product_id: str,
        variant_id: Optional[str] = None,
        quantity: int = 1
    ) -> ToolResult[Dict[str, Any]]:
        """
        Check inventory availability.
        
        Args:
            product_id: Product ID
            variant_id: Specific variant ID (optional)
            quantity: Quantity to check
        
        Returns:
            Availability information
        """
        try:
            if not self.product_service:
                return ToolResult.fail("Shopify client not configured")
            
            availability = await self.product_service.check_availability(
                product_id=product_id,
                variant_id=variant_id,
                quantity=quantity
            )
            
            return ToolResult.ok(
                data=availability,
                metadata={
                    "product_id": product_id,
                    "variant_id": variant_id,
                    "quantity_requested": quantity
                }
            )
            
        except Exception as e:
            self.log_error(e, "check_inventory_failed", product_id=product_id)
            return ToolResult.fail(f"Failed to check inventory: {str(e)}")