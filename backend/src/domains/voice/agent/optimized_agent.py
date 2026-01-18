"""Voice agent handler for Retell AI integration."""

from typing import Dict, Any, Optional
import logging

from domains.shopify.services.products import ProductService
from domains.shopify.services.inventory import InventoryService
from domains.shopify.services.carts import CartService
from integrations.shopify.client import ShopifyClient


logger = logging.getLogger(__name__)


class VoiceAgentHandler:
    """Handles tool execution for voice agent."""
    
    def __init__(self, shopify_client: ShopifyClient):
        self.shopify_client = shopify_client
        self.product_service = ProductService(shopify_client)
        self.inventory_service = InventoryService(shopify_client)
        self.cart_service = CartService(shopify_client)
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        logger.info(f"Executing tool: {tool_name} with params: {parameters}")
        
        try:
            if tool_name == "get_product_catalog":
                return await self._get_product_catalog(parameters)
            elif tool_name == "get_product_details":
                return await self._get_product_details(parameters)
            elif tool_name == "check_inventory":
                return await self._check_inventory(parameters)
            elif tool_name == "search_products":
                return await self._search_products(parameters)
            elif tool_name == "create_cart":
                return await self._create_cart(parameters)
            elif tool_name == "update_cart":
                return await self._update_cart(parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _get_product_catalog(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get product catalog."""
        limit = params.get("limit", 50)
        products = await self.product_service.get_all_products(limit=limit)
        
        formatted_products = []
        categories = set()
        min_price = float('inf')
        max_price = 0
        
        for product in products:
            if hasattr(product, 'to_dict'):
                product_dict = product.to_dict()
            else:
                product_dict = product.__dict__ if hasattr(product, '__dict__') else product
            
            formatted_products.append({
                "id": product_dict.get("id"),
                "title": product_dict.get("title"),
                "description": product_dict.get("body_html", ""),
                "price": self._get_product_price(product_dict),
                "vendor": product_dict.get("vendor"),
                "product_type": product_dict.get("product_type"),
                "available": self._is_product_available(product_dict)
            })
            
            if product_dict.get("product_type"):
                categories.add(product_dict["product_type"])
            
            price = self._get_product_price(product_dict)
            if price:
                min_price = min(min_price, price)
                max_price = max(max_price, price)
        
        return {
            "success": True,
            "products": formatted_products,
            "total_count": len(formatted_products),
            "categories": list(categories),
            "price_range": {
                "min": min_price if min_price != float('inf') else 0,
                "max": max_price
            }
        }
    
    async def _get_product_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed product information."""
        product_id = params.get("product_id")
        if not product_id:
            return {"success": False, "error": "product_id is required"}
        
        product = await self.product_service.get_product_details(
            product_id=product_id,
            include_inventory=True
        )
        
        if not product:
            return {"success": False, "error": "Product not found"}
        
        if hasattr(product, 'to_dict'):
            product_dict = product.to_dict()
        else:
            product_dict = product.__dict__ if hasattr(product, '__dict__') else product
        
        return {
            "success": True,
            "product": {
                "id": product_dict.get("id"),
                "title": product_dict.get("title"),
                "description": product_dict.get("body_html", ""),
                "price": self._get_product_price(product_dict),
                "variants": product_dict.get("variants", []),
                "images": product_dict.get("images", []),
                "vendor": product_dict.get("vendor"),
                "product_type": product_dict.get("product_type"),
                "tags": product_dict.get("tags", [])
            }
        }
    
    async def _check_inventory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check product inventory."""
        product_id = params.get("product_id")
        if not product_id:
            return {"success": False, "error": "product_id is required"}
        
        variant_id = params.get("variant_id")
        quantity = params.get("quantity", 1)
        
        availability = await self.inventory_service.check_availability(
            product_id=product_id,
            variant_id=variant_id,
            quantity=quantity
        )
        
        return {
            "success": True,
            **availability
        }
    
    async def _search_products(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search for products."""
        query = params.get("query", "")
        limit = params.get("limit", 10)
        
        products = await self.product_service.search_products(
            query=query,
            limit=limit
        )
        
        formatted_products = []
        for product in products:
            if hasattr(product, 'to_dict'):
                product_dict = product.to_dict()
            else:
                product_dict = product.__dict__ if hasattr(product, '__dict__') else product
            
            formatted_products.append({
                "id": product_dict.get("id"),
                "title": product_dict.get("title"),
                "description": product_dict.get("body_html", ""),
                "price": self._get_product_price(product_dict),
                "vendor": product_dict.get("vendor"),
                "product_type": product_dict.get("product_type")
            })
        
        return {
            "success": True,
            "products": formatted_products,
            "count": len(formatted_products)
        }
    
    async def _create_cart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new cart."""
        items = params.get("items", [])
        if not items:
            return {"success": False, "error": "items are required"}
        
        cart = await self.cart_service.create_cart(items)
        
        return {
            "success": True,
            "cart": cart
        }
    
    async def _update_cart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing cart."""
        cart_id = params.get("cart_id")
        items = params.get("items", [])
        
        if not cart_id:
            return {"success": False, "error": "cart_id is required"}
        
        cart = await self.cart_service.update_cart(cart_id, items)
        
        return {
            "success": True,
            "cart": cart
        }
    
    def _get_product_price(self, product: Dict[str, Any]) -> Optional[float]:
        """Extract product price from product data."""
        variants = product.get("variants", [])
        if variants and len(variants) > 0:
            return float(variants[0].get("price", 0))
        return None
    
    def _is_product_available(self, product: Dict[str, Any]) -> bool:
        """Check if product is available."""
        variants = product.get("variants", [])
        for variant in variants:
            if variant.get("inventory_quantity", 0) > 0:
                return True
        return False