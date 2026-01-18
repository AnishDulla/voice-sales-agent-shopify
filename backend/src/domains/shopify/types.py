"""Shopify domain types."""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ShopifyProduct(BaseModel):
    """Shopify product model."""
    
    id: str
    title: str
    body_html: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    handle: str
    tags: List[str] = Field(default_factory=list)
    status: str = "active"
    
    @field_validator('id', mode='before')
    @classmethod
    def convert_id_to_string(cls, v):
        return str(v) if v is not None else None
    
    @field_validator('tags', mode='before')
    @classmethod
    def convert_tags_to_list(cls, v):
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        elif isinstance(v, list):
            return v
        return []
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    images: List["ShopifyImage"] = Field(default_factory=list)
    variants: List["ShopifyVariant"] = Field(default_factory=list)
    options: List["ShopifyOption"] = Field(default_factory=list)
    
    def get_primary_variant(self) -> Optional["ShopifyVariant"]:
        """Get the primary (first available) variant."""
        return self.variants[0] if self.variants else None
    
    def get_price(self) -> float:
        """Get the primary price for this product."""
        variant = self.get_primary_variant()
        return variant.price if variant else 0.0
    
    def is_available(self) -> bool:
        """Check if product has any available variants."""
        return any(v.available for v in self.variants)


class ShopifyVariant(BaseModel):
    """Shopify product variant."""
    
    id: str
    product_id: str
    title: str
    
    @field_validator('id', 'product_id', mode='before')
    @classmethod
    def convert_ids_to_string(cls, v):
        return str(v) if v is not None else None
    price: float
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    grams: Optional[int] = None
    weight: Optional[float] = None
    weight_unit: Optional[str] = None
    inventory_quantity: Optional[int] = None
    available: bool = True
    option_values: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ShopifyImage(BaseModel):
    """Shopify product image."""
    
    id: str
    product_id: str
    src: str
    
    @field_validator('id', 'product_id', mode='before')
    @classmethod
    def convert_ids_to_string(cls, v):
        return str(v) if v is not None else None
    alt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ShopifyOption(BaseModel):
    """Shopify product option."""
    
    id: str
    product_id: str
    name: str
    
    @field_validator('id', 'product_id', mode='before')
    @classmethod
    def convert_ids_to_string(cls, v):
        return str(v) if v is not None else None
    values: List[str]


class ShopifyOrder(BaseModel):
    """Shopify order model."""
    
    id: str
    order_number: str
    email: Optional[str] = None
    phone: Optional[str] = None
    total_price: float
    subtotal_price: float
    total_tax: float
    currency: str
    financial_status: str
    fulfillment_status: Optional[str] = None
    line_items: List["ShopifyLineItem"] = Field(default_factory=list)
    shipping_address: Optional[Dict[str, Any]] = None
    billing_address: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class ShopifyLineItem(BaseModel):
    """Shopify order line item."""
    
    id: str
    product_id: Optional[str] = None
    variant_id: Optional[str] = None
    title: str
    variant_title: Optional[str] = None
    quantity: int
    price: float
    total_discount: float = 0.0
    sku: Optional[str] = None


class ShopifyCart(BaseModel):
    """Shopify cart representation."""
    
    token: str
    line_items: List[ShopifyLineItem] = Field(default_factory=list)
    note: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    total_price: float = 0.0
    total_weight: float = 0.0
    created_at: datetime
    updated_at: datetime


class ShopifyInventoryLevel(BaseModel):
    """Shopify inventory level."""
    
    inventory_item_id: str
    location_id: str
    available: int
    updated_at: datetime


class ShopifyLocation(BaseModel):
    """Shopify location."""
    
    id: str
    name: str
    address1: Optional[str] = None
    address2: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    phone: Optional[str] = None
    active: bool = True


class ShopifyCollection(BaseModel):
    """Shopify collection."""
    
    id: str
    title: str
    handle: str
    body_html: Optional[str] = None
    published_at: Optional[datetime] = None
    updated_at: datetime
    image: Optional[ShopifyImage] = None
    products_count: int = 0


class ShopifyCustomer(BaseModel):
    """Shopify customer."""
    
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    currency: Optional[str] = None
    total_spent: float = 0.0
    orders_count: int = 0
    verified_email: bool = False
    created_at: datetime
    updated_at: datetime


# Rebuild models for forward references
ShopifyProduct.model_rebuild()
ShopifyOrder.model_rebuild()
ShopifyCollection.model_rebuild()