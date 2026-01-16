"""Product-related tools for the agent."""

from typing import List, Optional, Dict, Any

from orchestration.tools.base import BaseTool, ToolContext
from orchestration.tools.registry import register_tool
from shared import (
    ToolResult,
    Product,
    SearchFilters,
    parse_price_range,
    normalize_product_query
)
from domains.shopify.client import ShopifyClient
from domains.shopify.products import ProductService


@register_tool(name="search_products", category="products", description="Search for products in the catalog")
class SearchProductsTool(BaseTool):
    """Tool for searching products."""
    
    name = "search_products"
    description = "Search for products by query, category, price range, and other filters"
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
        query: str,
        category: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        vendor: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        sort_by: str = "relevance"
    ) -> ToolResult[List[Product]]:
        """
        Search for products.
        
        Args:
            query: Search query (e.g., "running shoes")
            category: Product category filter
            price_min: Minimum price filter
            price_max: Maximum price filter
            vendor: Brand/vendor filter
            tags: Tag filters
            limit: Maximum number of results
            sort_by: Sort order (relevance, price_asc, price_desc)
        
        Returns:
            List of matching products
        """
        try:
            # Normalize query
            normalized_query = normalize_product_query(query)
            
            # Parse price range from query if not explicitly provided
            if not price_min and not price_max:
                price_range = parse_price_range(query)
                if price_range:
                    price_min, price_max = price_range
            
            # Create filters
            filters = SearchFilters(
                category=category,
                vendor=vendor,
                price_min=price_min,
                price_max=price_max,
                tags=tags or [],
                sort_by=sort_by,
                limit=limit
            )
            
            # Search products
            if not self.product_service:
                # Mock data for testing without Shopify connection
                return ToolResult.ok(
                    data=self._get_mock_products(normalized_query, filters),
                    metadata={"query": normalized_query, "filters": filters.dict()}
                )
            
            products = await self.product_service.search_products(
                query=normalized_query,
                filters=filters
            )
            
            return ToolResult.ok(
                data=products,
                metadata={
                    "query": normalized_query,
                    "filters": filters.dict(),
                    "count": len(products)
                }
            )
            
        except Exception as e:
            self.log_error(e, "search_products_failed", query=query)
            return ToolResult.fail(f"Failed to search products: {str(e)}")
    
    def _get_mock_products(self, query: str, filters: SearchFilters) -> List[Product]:
        """Get mock products for testing."""
        from shared import Product, ProductVariant
        
        mock_products = [
            Product(
                id="prod_001",
                title="Nike Air Zoom Pegasus 40",
                description="Responsive cushioning for everyday runs",
                vendor="Nike",
                product_type="Running Shoes",
                tags=["running", "mens", "cushioned"],
                price=130.00,
                images=["https://example.com/pegasus.jpg"],
                variants=[
                    ProductVariant(
                        id="var_001_1",
                        product_id="prod_001",
                        title="Size 10 - Black",
                        price=130.00,
                        available=True,
                        inventory_quantity=5,
                        options={"size": "10", "color": "Black"}
                    ),
                    ProductVariant(
                        id="var_001_2",
                        product_id="prod_001",
                        title="Size 11 - Black",
                        price=130.00,
                        available=True,
                        inventory_quantity=3,
                        options={"size": "11", "color": "Black"}
                    )
                ],
                available=True
            ),
            Product(
                id="prod_002",
                title="Adidas Ultraboost 23",
                description="Energy return with every step",
                vendor="Adidas",
                product_type="Running Shoes",
                tags=["running", "mens", "performance"],
                price=190.00,
                images=["https://example.com/ultraboost.jpg"],
                variants=[
                    ProductVariant(
                        id="var_002_1",
                        product_id="prod_002",
                        title="Size 10 - White",
                        price=190.00,
                        available=True,
                        inventory_quantity=2,
                        options={"size": "10", "color": "White"}
                    )
                ],
                available=True
            ),
            Product(
                id="prod_003",
                title="New Balance Fresh Foam 1080v13",
                description="Plush comfort for long runs",
                vendor="New Balance",
                product_type="Running Shoes",
                tags=["running", "mens", "comfort"],
                price=165.00,
                images=["https://example.com/freshfoam.jpg"],
                variants=[
                    ProductVariant(
                        id="var_003_1",
                        product_id="prod_003",
                        title="Size 10.5 - Grey",
                        price=165.00,
                        available=True,
                        inventory_quantity=7,
                        options={"size": "10.5", "color": "Grey"}
                    )
                ],
                available=True
            )
        ]
        
        # Filter by query
        if query:
            mock_products = [
                p for p in mock_products
                if query.lower() in p.title.lower() or
                query.lower() in (p.description or "").lower()
            ]
        
        # Apply filters
        if filters.price_min:
            mock_products = [p for p in mock_products if p.price >= filters.price_min]
        if filters.price_max:
            mock_products = [p for p in mock_products if p.price <= filters.price_max]
        if filters.vendor:
            mock_products = [p for p in mock_products if p.vendor and filters.vendor.lower() in p.vendor.lower()]
        
        return mock_products[:filters.limit]


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
                # Mock data for testing
                return ToolResult.ok(
                    data=self._get_mock_product_details(product_id),
                    metadata={"product_id": product_id}
                )
            
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
    
    def _get_mock_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get mock product details for testing."""
        from shared import Product, ProductVariant
        
        if product_id == "prod_001":
            product = Product(
                id="prod_001",
                title="Nike Air Zoom Pegasus 40",
                description="The Nike Air Zoom Pegasus 40 continues to put a spring in your step. Responsive cushioning in the forefoot and heel provides a bouncy sensation with every stride.",
                vendor="Nike",
                product_type="Running Shoes",
                tags=["running", "mens", "cushioned", "road-running"],
                price=130.00,
                images=[
                    "https://example.com/pegasus-1.jpg",
                    "https://example.com/pegasus-2.jpg"
                ],
                variants=[
                    ProductVariant(
                        id="var_001_1",
                        product_id="prod_001",
                        title="Size 10 - Black",
                        sku="NK-PEG40-BLK-10",
                        price=130.00,
                        available=True,
                        inventory_quantity=5,
                        options={"size": "10", "color": "Black"}
                    ),
                    ProductVariant(
                        id="var_001_2",
                        product_id="prod_001",
                        title="Size 11 - Black",
                        sku="NK-PEG40-BLK-11",
                        price=130.00,
                        available=True,
                        inventory_quantity=3,
                        options={"size": "11", "color": "Black"}
                    ),
                    ProductVariant(
                        id="var_001_3",
                        product_id="prod_001",
                        title="Size 10 - White",
                        sku="NK-PEG40-WHT-10",
                        price=130.00,
                        available=False,
                        inventory_quantity=0,
                        options={"size": "10", "color": "White"}
                    )
                ],
                available=True
            )
            
            return {
                "product": product.dict(),
                "variants_count": 3,
                "in_stock": True
            }
        
        return {
            "product": None,
            "error": "Product not found"
        }


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
                # Mock data for testing
                return ToolResult.ok(
                    data={
                        "available": True,
                        "quantity_available": 5,
                        "message": "Product is in stock"
                    },
                    metadata={
                        "product_id": product_id,
                        "variant_id": variant_id,
                        "quantity_requested": quantity
                    }
                )
            
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