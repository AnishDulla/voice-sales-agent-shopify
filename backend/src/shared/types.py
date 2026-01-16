"""Shared type definitions across the application."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypeVar, Generic
from pydantic import BaseModel, Field


T = TypeVar("T")


class ResponseStatus(str, Enum):
    """Standard response statuses."""
    
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class Message(BaseModel):
    """Conversation message."""
    
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ConversationContext(BaseModel):
    """Context maintained across conversation."""
    
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    cart_items: List[Dict[str, Any]] = Field(default_factory=list)
    viewed_products: List[str] = Field(default_factory=list)


@dataclass
class ToolResult(Generic[T]):
    """Standard result from tool execution."""
    
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def ok(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> "ToolResult[T]":
        """Create successful result."""
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, metadata: Optional[Dict[str, Any]] = None) -> "ToolResult[T]":
        """Create failed result."""
        return cls(success=False, error=error, metadata=metadata)


class Product(BaseModel):
    """Product model."""
    
    id: str
    title: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    price: float
    currency: str = "USD"
    images: List[str] = Field(default_factory=list)
    variants: List["ProductVariant"] = Field(default_factory=list)
    available: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProductVariant(BaseModel):
    """Product variant model."""
    
    id: str
    product_id: str
    title: str
    sku: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    available: bool = True
    inventory_quantity: Optional[int] = None
    options: Dict[str, str] = Field(default_factory=dict)  # e.g., {"size": "M", "color": "Blue"}
    image_id: Optional[str] = None


class CartItem(BaseModel):
    """Cart item model."""
    
    product_id: str
    variant_id: str
    quantity: int = 1
    price: float
    title: str
    variant_title: Optional[str] = None
    image_url: Optional[str] = None


class Cart(BaseModel):
    """Shopping cart model."""
    
    id: str
    session_id: str
    items: List[CartItem] = Field(default_factory=list)
    subtotal: float = 0.0
    tax: float = 0.0
    shipping: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def calculate_totals(self) -> None:
        """Recalculate cart totals."""
        self.subtotal = sum(item.price * item.quantity for item in self.items)
        self.total = self.subtotal + self.tax + self.shipping
        self.updated_at = datetime.utcnow()




class Intent(str, Enum):
    """User intent types."""
    
    PRODUCT_SEARCH = "product_search"
    PRODUCT_DETAILS = "product_details"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    VIEW_CART = "view_cart"
    CHECKOUT = "checkout"
    SIZING_HELP = "sizing_help"
    RECOMMENDATION = "recommendation"
    POLICY_INQUIRY = "policy_inquiry"
    GENERAL_HELP = "general_help"
    UNKNOWN = "unknown"


class AgentState(BaseModel):
    """Agent conversation state."""
    
    session_id: str
    current_intent: Intent = Intent.UNKNOWN
    context: ConversationContext
    last_tool_results: Optional[Dict[str, Any]] = None
    pending_confirmation: Optional[Dict[str, Any]] = None
    error_count: int = 0
    
    class Config:
        use_enum_values = True


# Re-export for backwards compatibility
ProductVariant.model_rebuild()