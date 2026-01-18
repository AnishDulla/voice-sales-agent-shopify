"""Shopify API client wrapper."""

import httpx
from typing import Dict, Any, List, Optional
import logging


logger = logging.getLogger(__name__)


class ShopifyClient:
    """Client for Shopify Admin API."""
    
    def __init__(self, store_url: str, access_token: str, api_version: str = "2024-01"):
        self.store_url = store_url.rstrip('/')
        if not self.store_url.startswith('https://'):
            self.store_url = f"https://{self.store_url}"
        
        self.base_url = f"{self.store_url}/admin/api/{api_version}"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get_products(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all products."""
        try:
            response = await self.client.get(
                f"{self.base_url}/products.json",
                params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("products", [])
        except Exception as e:
            logger.error(f"Failed to fetch products: {e}")
            return []
    
    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a single product by ID."""
        try:
            response = await self.client.get(
                f"{self.base_url}/products/{product_id}.json"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("product")
        except Exception as e:
            logger.error(f"Failed to fetch product {product_id}: {e}")
            return None
    
    async def search_products(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products."""
        try:
            # For now, we'll fetch all products and filter locally
            # In production, you'd want to use Shopify's search API
            all_products = await self.get_products(limit=250)
            
            query_lower = query.lower()
            matching_products = []
            
            for product in all_products:
                title = product.get("title", "").lower()
                body = product.get("body_html", "").lower()
                vendor = product.get("vendor", "").lower()
                product_type = product.get("product_type", "").lower()
                tags = " ".join(product.get("tags", "").split(",")).lower()
                
                if (query_lower in title or 
                    query_lower in body or 
                    query_lower in vendor or
                    query_lower in product_type or
                    query_lower in tags):
                    matching_products.append(product)
                    
                if len(matching_products) >= limit:
                    break
            
            return matching_products
        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            return []
    
    async def get_collections(self) -> List[Dict[str, Any]]:
        """Get all collections."""
        try:
            response = await self.client.get(
                f"{self.base_url}/custom_collections.json"
            )
            response.raise_for_status()
            data = response.json()
            
            custom_collections = data.get("custom_collections", [])
            
            # Also get smart collections
            response = await self.client.get(
                f"{self.base_url}/smart_collections.json"
            )
            if response.status_code == 200:
                data = response.json()
                smart_collections = data.get("smart_collections", [])
                return custom_collections + smart_collections
            
            return custom_collections
        except Exception as e:
            logger.error(f"Failed to fetch collections: {e}")
            return []
    
    async def check_inventory(
        self,
        product_id: str,
        variant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check inventory for a product."""
        try:
            product = await self.get_product(product_id)
            if not product:
                return {"available": False, "error": "Product not found"}
            
            variants = product.get("variants", [])
            
            if variant_id:
                # Check specific variant
                for variant in variants:
                    if str(variant.get("id")) == str(variant_id):
                        return {
                            "available": variant.get("inventory_quantity", 0) > 0,
                            "quantity": variant.get("inventory_quantity", 0),
                            "variant": variant
                        }
                return {"available": False, "error": "Variant not found"}
            else:
                # Check all variants
                total_quantity = sum(
                    v.get("inventory_quantity", 0) for v in variants
                )
                available_variants = [
                    v for v in variants if v.get("inventory_quantity", 0) > 0
                ]
                
                return {
                    "available": total_quantity > 0,
                    "total_quantity": total_quantity,
                    "available_variants": available_variants,
                    "all_variants": variants
                }
        except Exception as e:
            logger.error(f"Failed to check inventory: {e}")
            return {"available": False, "error": str(e)}
    
    async def create_draft_order(self, line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a draft order."""
        try:
            order_data = {
                "draft_order": {
                    "line_items": line_items,
                    "note": "Created via Voice Commerce API"
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/draft_orders.json",
                json=order_data
            )
            response.raise_for_status()
            data = response.json()
            return data.get("draft_order", {})
        except Exception as e:
            logger.error(f"Failed to create draft order: {e}")
            return {"error": str(e)}