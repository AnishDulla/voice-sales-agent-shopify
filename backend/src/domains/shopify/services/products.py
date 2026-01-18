"""Product service for Shopify domain."""

from typing import List, Dict, Any, Optional
import logging
from integrations.shopify.client import ShopifyClient


logger = logging.getLogger(__name__)


class ProductService:
    """Service for product-related operations."""
    
    def __init__(self, shopify_client: ShopifyClient):
        self.client = shopify_client
    
    async def get_all_products(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all products."""
        return await self.client.get_products(limit=limit)
    
    async def get_product_details(
        self,
        product_id: str,
        include_inventory: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get detailed product information."""
        product = await self.client.get_product(product_id)
        
        if product and include_inventory:
            inventory = await self.client.check_inventory(product_id)
            product["inventory"] = inventory
        
        return product
    
    async def search_products(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for products."""
        products = await self.client.search_products(query, limit)
        
        # Apply additional filters if provided
        if filters:
            filtered_products = []
            for product in products:
                match = True
                
                if "min_price" in filters:
                    variants = product.get("variants", [])
                    if variants:
                        min_product_price = min(
                            float(v.get("price", 0)) for v in variants
                        )
                        if min_product_price < filters["min_price"]:
                            match = False
                
                if "max_price" in filters:
                    variants = product.get("variants", [])
                    if variants:
                        max_product_price = max(
                            float(v.get("price", 0)) for v in variants
                        )
                        if max_product_price > filters["max_price"]:
                            match = False
                
                if "vendor" in filters and product.get("vendor") != filters["vendor"]:
                    match = False
                
                if "product_type" in filters and product.get("product_type") != filters["product_type"]:
                    match = False
                
                if match:
                    filtered_products.append(product)
            
            return filtered_products
        
        return products
    
    async def get_product_recommendations(
        self,
        product_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get product recommendations based on a product."""
        # Get the original product
        product = await self.client.get_product(product_id)
        if not product:
            return []
        
        # Get products of the same type
        product_type = product.get("product_type")
        vendor = product.get("vendor")
        
        all_products = await self.client.get_products(limit=100)
        
        recommendations = []
        for p in all_products:
            if str(p.get("id")) == str(product_id):
                continue
            
            score = 0
            if p.get("product_type") == product_type:
                score += 2
            if p.get("vendor") == vendor:
                score += 1
            
            if score > 0:
                recommendations.append((score, p))
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in recommendations[:limit]]