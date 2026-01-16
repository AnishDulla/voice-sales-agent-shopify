"""Shopify products domain logic."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from shared import Product
from .client import ShopifyClient
from .types import ShopifyProduct


class ProductService:
    """Service for product-related operations."""
    
    def __init__(self, client: ShopifyClient):
        self.client = client
    
    
    async def get_product_details(
        self,
        product_id: str,
        include_inventory: bool = False
    ) -> Optional[Product]:
        """Get detailed product information."""
        shopify_product = await self.client.get_product(product_id)
        
        if not shopify_product:
            return None
        
        product = shopify_product.to_domain_product()
        
        # Get inventory if requested
        if include_inventory and shopify_product.variants:
            inventory_item_ids = [
                v.id for v in shopify_product.variants
            ]
            
            inventory_levels = await self.client.get_inventory_levels(
                inventory_item_ids=inventory_item_ids
            )
            
            # Update variant inventory
            inventory_map = {
                level.inventory_item_id: level.available
                for level in inventory_levels
            }
            
            for variant in product.variants:
                if variant.id in inventory_map:
                    variant.inventory_quantity = inventory_map[variant.id]
        
        return product
    
    async def get_products_by_category(
        self,
        category: str,
        limit: int = 10
    ) -> List[Product]:
        """Get products by category."""
        shopify_products = await self.client.get_products(
            product_type=category,
            limit=limit
        )
        
        return [p.to_domain_product() for p in shopify_products]
    
    async def get_all_products(self, limit: int = 50) -> List[Product]:
        """Get all products in the catalog for intelligent LLM filtering."""
        shopify_products = await self.client.get_products(limit=limit)
        return [p.to_domain_product() for p in shopify_products]
    
    async def get_products_by_vendor(
        self,
        vendor: str,
        limit: int = 10
    ) -> List[Product]:
        """Get products by vendor/brand."""
        shopify_products = await self.client.get_products(
            vendor=vendor,
            limit=limit
        )
        
        return [p.to_domain_product() for p in shopify_products]
    
    async def get_related_products(
        self,
        product: Product,
        limit: int = 5
    ) -> List[Product]:
        """Get related products based on tags and category."""
        # Get products with similar tags
        all_products = await self.client.get_products(limit=100)
        domain_products = [p.to_domain_product() for p in all_products]
        
        # Calculate similarity scores
        related = []
        for p in domain_products:
            if p.id == product.id:
                continue
            
            score = 0
            
            # Same category
            if p.product_type == product.product_type:
                score += 10
            
            # Same vendor
            if p.vendor == product.vendor:
                score += 5
            
            # Shared tags
            shared_tags = set(p.tags) & set(product.tags)
            score += len(shared_tags) * 3
            
            # Similar price range
            price_diff = abs(p.price - product.price)
            if price_diff < product.price * 0.2:  # Within 20%
                score += 5
            
            if score > 0:
                related.append((score, p))
        
        # Sort by score and return top matches
        related.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in related[:limit]]
    
    
    
    async def check_availability(
        self,
        product_id: str,
        variant_id: Optional[str] = None,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Check product/variant availability."""
        product = await self.get_product_details(
            product_id,
            include_inventory=True
        )
        
        if not product:
            return {
                "available": False,
                "reason": "Product not found"
            }
        
        if variant_id:
            # Check specific variant
            variant = next(
                (v for v in product.variants if v.id == variant_id),
                None
            )
            
            if not variant:
                return {
                    "available": False,
                    "reason": "Variant not found"
                }
            
            if not variant.available:
                return {
                    "available": False,
                    "reason": "Variant not available"
                }
            
            if variant.inventory_quantity is not None:
                if variant.inventory_quantity < quantity:
                    return {
                        "available": False,
                        "reason": f"Only {variant.inventory_quantity} in stock",
                        "available_quantity": variant.inventory_quantity
                    }
            
            return {
                "available": True,
                "variant": variant.dict(),
                "quantity_available": variant.inventory_quantity
            }
        
        else:
            # Check any variant availability
            available_variants = [
                v for v in product.variants
                if v.available and (
                    v.inventory_quantity is None or
                    v.inventory_quantity >= quantity
                )
            ]
            
            if not available_variants:
                return {
                    "available": False,
                    "reason": "No variants available"
                }
            
            return {
                "available": True,
                "available_variants": [v.dict() for v in available_variants],
                "total_variants": len(product.variants)
            }