"""Shopify Admin API client."""

import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from shared import (
    ShopifyAPIError,
    RateLimitError,
    retry_async,
    get_logger,
    LoggerMixin
)
from .types import (
    ShopifyProduct,
    ShopifyVariant,
    ShopifyOrder,
    ShopifyInventoryLevel,
    ShopifyCollection,
    ShopifyCustomer
)


logger = get_logger(__name__)


class ShopifyClient(LoggerMixin):
    """Client for interacting with Shopify Admin API."""
    
    def __init__(
        self,
        store_url: str,
        access_token: str,
        api_version: str = "2024-01"
    ):
        self.store_url = store_url.rstrip("/")
        self.access_token = access_token
        self.api_version = api_version
        self.base_url = f"https://{store_url}/admin/api/{api_version}"
        
        self.client = httpx.AsyncClient(
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make an API request with error handling."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data
            )
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise RateLimitError(
                    resource="Shopify API",
                    retry_after=int(retry_after)
                )
            
            # Check for errors
            if response.status_code >= 400:
                raise ShopifyAPIError(
                    message=f"API request failed: {response.text}",
                    status_code=response.status_code,
                    response=response.json() if response.text else None
                )
            
            return response.json()
            
        except httpx.RequestError as e:
            raise ShopifyAPIError(
                message=f"Request failed: {str(e)}",
                status_code=None
            )
    
    @retry_async(max_attempts=3, delay=1.0)
    async def get_products(
        self,
        limit: int = 50,
        product_type: Optional[str] = None,
        vendor: Optional[str] = None,
        status: str = "active",
        collection_id: Optional[str] = None
    ) -> List[ShopifyProduct]:
        """Get products from Shopify."""
        params = {
            "limit": min(limit, 250),
            "status": status
        }
        
        if product_type:
            params["product_type"] = product_type
        if vendor:
            params["vendor"] = vendor
        if collection_id:
            params["collection_id"] = collection_id
        
        self.log_event(
            "fetching_products",
            params=params
        )
        
        response = await self._request("GET", "products.json", params=params)
        products_data = response.get("products", [])
        
        products = []
        for data in products_data:
            try:
                # Parse dates
                data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
                data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
                if data.get("published_at"):
                    data["published_at"] = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
                
                # Parse variants
                for variant in data.get("variants", []):
                    variant["created_at"] = datetime.fromisoformat(variant["created_at"].replace("Z", "+00:00"))
                    variant["updated_at"] = datetime.fromisoformat(variant["updated_at"].replace("Z", "+00:00"))
                    variant["price"] = float(variant["price"])
                    if variant.get("compare_at_price"):
                        variant["compare_at_price"] = float(variant["compare_at_price"])
                
                # Parse images
                for image in data.get("images", []):
                    image["created_at"] = datetime.fromisoformat(image["created_at"].replace("Z", "+00:00"))
                    image["updated_at"] = datetime.fromisoformat(image["updated_at"].replace("Z", "+00:00"))
                
                products.append(ShopifyProduct(**data))
            except Exception as e:
                self.log_error(e, "product_parse_error", product_id=data.get("id"))
        
        return products
    
    async def get_product(self, product_id: str) -> Optional[ShopifyProduct]:
        """Get a single product by ID."""
        try:
            response = await self._request("GET", f"products/{product_id}.json")
            data = response.get("product")
            
            if not data:
                return None
            
            # Parse dates
            data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            if data.get("published_at"):
                data["published_at"] = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
            
            # Parse nested objects
            for variant in data.get("variants", []):
                variant["created_at"] = datetime.fromisoformat(variant["created_at"].replace("Z", "+00:00"))
                variant["updated_at"] = datetime.fromisoformat(variant["updated_at"].replace("Z", "+00:00"))
                variant["price"] = float(variant["price"])
                if variant.get("compare_at_price"):
                    variant["compare_at_price"] = float(variant["compare_at_price"])
            
            for image in data.get("images", []):
                image["created_at"] = datetime.fromisoformat(image["created_at"].replace("Z", "+00:00"))
                image["updated_at"] = datetime.fromisoformat(image["updated_at"].replace("Z", "+00:00"))
            
            return ShopifyProduct(**data)
            
        except ShopifyAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def search_products(
        self,
        query: str,
        limit: int = 10
    ) -> List[ShopifyProduct]:
        """Search products using Shopify's search API."""
        # Note: This is a simplified version. Real implementation would use
        # Shopify's GraphQL API for better search capabilities
        
        self.log_event(
            "searching_products",
            query=query,
            limit=limit
        )
        
        # Get all products and filter locally (simplified)
        all_products = await self.get_products(limit=250)
        
        query_lower = query.lower()
        matching_products = []
        
        for product in all_products:
            # Simple text matching
            if (
                query_lower in product.title.lower() or
                (product.body_html and query_lower in product.body_html.lower()) or
                any(query_lower in tag.lower() for tag in product.tags) or
                (product.vendor and query_lower in product.vendor.lower())
            ):
                matching_products.append(product)
        
        # Sort by relevance (simplified)
        matching_products.sort(
            key=lambda p: (
                query_lower in p.title.lower(),
                len(p.title)
            ),
            reverse=True
        )
        
        return matching_products[:limit]
    
    async def get_inventory_levels(
        self,
        inventory_item_ids: List[str],
        location_ids: Optional[List[str]] = None
    ) -> List[ShopifyInventoryLevel]:
        """Get inventory levels for items."""
        params = {
            "inventory_item_ids": ",".join(inventory_item_ids)
        }
        
        if location_ids:
            params["location_ids"] = ",".join(location_ids)
        
        response = await self._request("GET", "inventory_levels.json", params=params)
        levels_data = response.get("inventory_levels", [])
        
        levels = []
        for data in levels_data:
            data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            levels.append(ShopifyInventoryLevel(**data))
        
        return levels
    
    async def get_collections(self, limit: int = 50) -> List[ShopifyCollection]:
        """Get collections from Shopify."""
        params = {"limit": min(limit, 250)}
        
        response = await self._request("GET", "custom_collections.json", params=params)
        collections_data = response.get("custom_collections", [])
        
        # Also get smart collections
        smart_response = await self._request("GET", "smart_collections.json", params=params)
        collections_data.extend(smart_response.get("smart_collections", []))
        
        collections = []
        for data in collections_data:
            data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            if data.get("published_at"):
                data["published_at"] = datetime.fromisoformat(data["published_at"].replace("Z", "+00:00"))
            
            if data.get("image"):
                image = data["image"]
                image["created_at"] = datetime.utcnow()  # Not provided by API
                image["updated_at"] = datetime.utcnow()
                image["id"] = str(image.get("id", ""))
                image["product_id"] = ""
            
            collections.append(ShopifyCollection(**data))
        
        return collections
    
    async def create_cart(self, line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a cart (draft order in Shopify)."""
        # Note: Shopify doesn't have a cart API directly
        # This would typically create a draft order or use Storefront API
        
        draft_order_data = {
            "draft_order": {
                "line_items": line_items,
                "use_customer_default_address": True
            }
        }
        
        response = await self._request(
            "POST",
            "draft_orders.json",
            json_data=draft_order_data
        )
        
        return response.get("draft_order", {})
    
    async def update_cart(
        self,
        cart_id: str,
        line_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update a cart (draft order)."""
        draft_order_data = {
            "draft_order": {
                "line_items": line_items
            }
        }
        
        response = await self._request(
            "PUT",
            f"draft_orders/{cart_id}.json",
            json_data=draft_order_data
        )
        
        return response.get("draft_order", {})