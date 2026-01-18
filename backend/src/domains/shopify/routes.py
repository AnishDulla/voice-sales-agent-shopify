"""Shopify domain API routes."""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from domains.shopify.services.products import ProductService
from domains.shopify.services.inventory import InventoryService
from domains.shopify.services.carts import CartService


router = APIRouter()
logger = logging.getLogger(__name__)


class SearchRequest(BaseModel):
    """Search request model."""
    query: str
    limit: int = 10
    filters: Optional[Dict[str, Any]] = None


class CartItemRequest(BaseModel):
    """Cart item request model."""
    variant_id: str
    quantity: int = 1
    product_id: Optional[str] = None


@router.get("/products")
async def get_products(
    request: Request,
    limit: int = Query(50, le=250)
) -> Dict[str, Any]:
    """Get all products."""
    from app import shopify_client
    service = ProductService(shopify_client)
    products = await service.get_all_products(limit=limit)
    
    return {
        "products": products,
        "count": len(products)
    }


@router.get("/products/{product_id}")
async def get_product(
    request: Request,
    product_id: str,
    include_inventory: bool = Query(False)
) -> Dict[str, Any]:
    """Get a single product."""
    from app import shopify_client
    service = ProductService(shopify_client)
    product = await service.get_product_details(
        product_id=product_id,
        include_inventory=include_inventory
    )
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return product


@router.post("/products/search")
async def search_products(
    request: Request,
    search_request: SearchRequest
) -> Dict[str, Any]:
    """Search products."""
    from app import shopify_client
    service = ProductService(shopify_client)
    products = await service.search_products(
        query=search_request.query,
        limit=search_request.limit,
        filters=search_request.filters
    )
    
    return {
        "query": search_request.query,
        "products": products,
        "count": len(products)
    }


@router.get("/products/{product_id}/recommendations")
async def get_product_recommendations(
    request: Request,
    product_id: str,
    limit: int = Query(5, le=20)
) -> Dict[str, Any]:
    """Get product recommendations."""
    from app import shopify_client
    service = ProductService(shopify_client)
    recommendations = await service.get_product_recommendations(
        product_id=product_id,
        limit=limit
    )
    
    return {
        "product_id": product_id,
        "recommendations": recommendations,
        "count": len(recommendations)
    }


@router.get("/products/{product_id}/inventory")
async def check_product_inventory(
    request: Request,
    product_id: str,
    variant_id: Optional[str] = Query(None),
    quantity: int = Query(1, ge=1)
) -> Dict[str, Any]:
    """Check product inventory."""
    from app import shopify_client
    service = InventoryService(shopify_client)
    availability = await service.check_availability(
        product_id=product_id,
        variant_id=variant_id,
        quantity=quantity
    )
    
    return availability


@router.get("/inventory/low-stock")
async def get_low_stock_products(
    request: Request,
    threshold: int = Query(5, ge=0)
) -> Dict[str, Any]:
    """Get low stock products."""
    from app import shopify_client
    service = InventoryService(shopify_client)
    low_stock = await service.get_low_stock_products(threshold=threshold)
    
    return {
        "threshold": threshold,
        "products": low_stock,
        "count": len(low_stock)
    }


@router.get("/collections")
async def get_collections(request: Request) -> Dict[str, Any]:
    """Get all collections."""
    from app import shopify_client
    collections = await shopify_client.get_collections()
    
    return {
        "collections": collections,
        "count": len(collections)
    }


@router.post("/carts")
async def create_cart(
    request: Request,
    items: List[CartItemRequest] = None
) -> Dict[str, Any]:
    """Create a new cart."""
    from app import shopify_client
    service = CartService(shopify_client)
    
    cart_items = []
    if items:
        for item in items:
            cart_items.append(item.dict())
    
    cart = await service.create_cart(cart_items)
    return cart


@router.get("/carts/{cart_id}")
async def get_cart(
    request: Request,
    cart_id: str
) -> Dict[str, Any]:
    """Get a cart."""
    from app import shopify_client
    service = CartService(shopify_client)
    cart = await service.get_cart(cart_id)
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    return cart


@router.post("/carts/{cart_id}/items")
async def add_to_cart(
    request: Request,
    cart_id: str,
    item: CartItemRequest
) -> Dict[str, Any]:
    """Add item to cart."""
    from app import shopify_client
    service = CartService(shopify_client)
    cart = await service.add_to_cart(
        cart_id=cart_id,
        variant_id=item.variant_id,
        quantity=item.quantity,
        product_id=item.product_id
    )
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    return cart


@router.delete("/carts/{cart_id}/items/{variant_id}")
async def remove_from_cart(
    request: Request,
    cart_id: str,
    variant_id: str
) -> Dict[str, Any]:
    """Remove item from cart."""
    from app import shopify_client
    service = CartService(shopify_client)
    cart = await service.remove_from_cart(cart_id, variant_id)
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    return cart


@router.post("/carts/{cart_id}/checkout")
async def checkout_cart(
    request: Request,
    cart_id: str
) -> Dict[str, Any]:
    """Checkout cart to draft order."""
    from app import shopify_client
    service = CartService(shopify_client)
    result = await service.checkout_cart(cart_id)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result