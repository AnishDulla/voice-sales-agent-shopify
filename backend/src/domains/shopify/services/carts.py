"""Cart service for Shopify domain."""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from integrations.shopify.client import ShopifyClient


logger = logging.getLogger(__name__)


class CartService:
    """Service for cart-related operations."""
    
    def __init__(self, shopify_client: ShopifyClient):
        self.client = shopify_client
        # In-memory cart storage (in production, use Redis or database)
        self.carts: Dict[str, Dict[str, Any]] = {}
    
    async def create_cart(
        self,
        items: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new cart."""
        import uuid
        cart_id = str(uuid.uuid4())
        
        cart = {
            "id": cart_id,
            "items": items or [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "total": 0.0
        }
        
        if items:
            cart = await self._calculate_cart_total(cart)
        
        self.carts[cart_id] = cart
        return cart
    
    async def get_cart(self, cart_id: str) -> Optional[Dict[str, Any]]:
        """Get a cart by ID."""
        return self.carts.get(cart_id)
    
    async def update_cart(
        self,
        cart_id: str,
        items: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Update cart items."""
        cart = self.carts.get(cart_id)
        if not cart:
            return None
        
        cart["items"] = items
        cart["updated_at"] = datetime.utcnow().isoformat()
        cart = await self._calculate_cart_total(cart)
        
        self.carts[cart_id] = cart
        return cart
    
    async def add_to_cart(
        self,
        cart_id: str,
        variant_id: str,
        quantity: int = 1,
        product_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Add an item to the cart."""
        cart = self.carts.get(cart_id)
        if not cart:
            return None
        
        # Check if item already exists in cart
        existing_item = None
        for item in cart["items"]:
            if item.get("variant_id") == variant_id:
                existing_item = item
                break
        
        if existing_item:
            existing_item["quantity"] += quantity
        else:
            # Get product and variant details
            product_info = None
            if product_id:
                product = await self.client.get_product(product_id)
                if product:
                    for variant in product.get("variants", []):
                        if str(variant.get("id")) == str(variant_id):
                            product_info = {
                                "product_title": product.get("title"),
                                "variant_title": variant.get("title"),
                                "price": float(variant.get("price", 0))
                            }
                            break
            
            new_item = {
                "variant_id": variant_id,
                "product_id": product_id,
                "quantity": quantity
            }
            
            if product_info:
                new_item.update(product_info)
            
            cart["items"].append(new_item)
        
        cart["updated_at"] = datetime.utcnow().isoformat()
        cart = await self._calculate_cart_total(cart)
        
        self.carts[cart_id] = cart
        return cart
    
    async def remove_from_cart(
        self,
        cart_id: str,
        variant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Remove an item from the cart."""
        cart = self.carts.get(cart_id)
        if not cart:
            return None
        
        cart["items"] = [
            item for item in cart["items"] 
            if item.get("variant_id") != variant_id
        ]
        
        cart["updated_at"] = datetime.utcnow().isoformat()
        cart = await self._calculate_cart_total(cart)
        
        self.carts[cart_id] = cart
        return cart
    
    async def checkout_cart(
        self,
        cart_id: str
    ) -> Dict[str, Any]:
        """Convert cart to a draft order."""
        cart = self.carts.get(cart_id)
        if not cart:
            return {"error": "Cart not found"}
        
        if not cart["items"]:
            return {"error": "Cart is empty"}
        
        # Prepare line items for draft order
        line_items = []
        for item in cart["items"]:
            line_item = {
                "variant_id": item["variant_id"],
                "quantity": item["quantity"]
            }
            line_items.append(line_item)
        
        # Create draft order
        draft_order = await self.client.create_draft_order(line_items)
        
        if not draft_order.get("error"):
            # Clear the cart after successful checkout
            del self.carts[cart_id]
        
        return draft_order
    
    async def _calculate_cart_total(
        self,
        cart: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate cart total."""
        total = 0.0
        
        for item in cart["items"]:
            if "price" in item:
                total += item["price"] * item["quantity"]
            else:
                # Try to fetch price if not cached
                if item.get("product_id"):
                    product = await self.client.get_product(item["product_id"])
                    if product:
                        for variant in product.get("variants", []):
                            if str(variant.get("id")) == str(item["variant_id"]):
                                price = float(variant.get("price", 0))
                                item["price"] = price
                                total += price * item["quantity"]
                                break
        
        cart["total"] = total
        return cart