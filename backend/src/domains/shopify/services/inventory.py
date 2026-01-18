"""Inventory service for Shopify domain."""

from typing import Dict, Any, Optional, List
import logging
from integrations.shopify.client import ShopifyClient


logger = logging.getLogger(__name__)


class InventoryService:
    """Service for inventory-related operations."""
    
    def __init__(self, shopify_client: ShopifyClient):
        self.client = shopify_client
    
    async def check_availability(
        self,
        product_id: str,
        variant_id: Optional[str] = None,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Check if a product/variant is available in the requested quantity."""
        inventory = await self.client.check_inventory(product_id, variant_id)
        
        if not inventory.get("available"):
            return {
                "available": False,
                "message": inventory.get("error", "Product not available"),
                "requested_quantity": quantity,
                "available_quantity": 0
            }
        
        if variant_id:
            # Check specific variant
            variant = inventory.get("variant", {})
            available_qty = variant.get("inventory_quantity", 0)
            
            return {
                "available": available_qty >= quantity,
                "requested_quantity": quantity,
                "available_quantity": available_qty,
                "variant": variant,
                "message": (
                    f"Available" if available_qty >= quantity 
                    else f"Only {available_qty} available"
                )
            }
        else:
            # Check total inventory across all variants
            total_qty = inventory.get("total_quantity", 0)
            
            return {
                "available": total_qty >= quantity,
                "requested_quantity": quantity,
                "available_quantity": total_qty,
                "available_variants": inventory.get("available_variants", []),
                "message": (
                    f"Available" if total_qty >= quantity 
                    else f"Only {total_qty} available"
                )
            }
    
    async def get_low_stock_products(
        self,
        threshold: int = 5
    ) -> List[Dict[str, Any]]:
        """Get products with low stock."""
        products = await self.client.get_products(limit=250)
        low_stock_products = []
        
        for product in products:
            variants = product.get("variants", [])
            total_inventory = sum(
                v.get("inventory_quantity", 0) for v in variants
            )
            
            if 0 < total_inventory <= threshold:
                low_stock_products.append({
                    "product": product,
                    "total_inventory": total_inventory,
                    "variants_low_stock": [
                        v for v in variants 
                        if 0 < v.get("inventory_quantity", 0) <= threshold
                    ]
                })
        
        return low_stock_products
    
    async def check_variant_availability(
        self,
        variant_id: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        """Check availability for a specific variant ID."""
        # In a real implementation, we'd have a direct variant endpoint
        # For now, we'll search through products
        products = await self.client.get_products(limit=250)
        
        for product in products:
            for variant in product.get("variants", []):
                if str(variant.get("id")) == str(variant_id):
                    available_qty = variant.get("inventory_quantity", 0)
                    return {
                        "available": available_qty >= quantity,
                        "requested_quantity": quantity,
                        "available_quantity": available_qty,
                        "variant": variant,
                        "product": product,
                        "message": (
                            f"Available" if available_qty >= quantity 
                            else f"Only {available_qty} available"
                        )
                    }
        
        return {
            "available": False,
            "message": "Variant not found",
            "requested_quantity": quantity,
            "available_quantity": 0
        }