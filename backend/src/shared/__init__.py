"""Shared module for common utilities and types."""

from .types import (
    ResponseStatus,
    Message,
    ConversationContext,
    ToolResult,
    Product,
    ProductVariant,
    CartItem,
    Cart,
    SearchFilters,
    Intent,
    AgentState,
)

from .exceptions import (
    VoiceAgentException,
    ToolExecutionError,
    ToolNotFoundError,
    ShopifyAPIError,
    VoiceProcessingError,
    SessionError,
    ConfigurationError,
    RateLimitError,
    ValidationError,
)

from .logging import (
    setup_logging,
    get_logger,
    LoggerMixin,
    RequestLogger,
    log_tool_execution,
)

from .utils import (
    generate_id,
    generate_session_id,
    generate_request_id,
    sanitize_text,
    normalize_product_query,
    calculate_cache_key,
    parse_price_range,
    extract_number,
    format_price,
    truncate_text,
    retry_async,
    batch_items,
    merge_dicts,
    calculate_similarity,
    Timer,
    safe_json_loads,
    create_error_response,
)

__all__ = [
    # Types
    "ResponseStatus",
    "Message",
    "ConversationContext",
    "ToolResult",
    "Product",
    "ProductVariant",
    "CartItem",
    "Cart",
    "SearchFilters",
    "Intent",
    "AgentState",
    # Exceptions
    "VoiceAgentException",
    "ToolExecutionError",
    "ToolNotFoundError",
    "ShopifyAPIError",
    "VoiceProcessingError",
    "SessionError",
    "ConfigurationError",
    "RateLimitError",
    "ValidationError",
    # Logging
    "setup_logging",
    "get_logger",
    "LoggerMixin",
    "RequestLogger",
    "log_tool_execution",
    # Utils
    "generate_id",
    "generate_session_id",
    "generate_request_id",
    "sanitize_text",
    "normalize_product_query",
    "calculate_cache_key",
    "parse_price_range",
    "extract_number",
    "format_price",
    "truncate_text",
    "retry_async",
    "batch_items",
    "merge_dicts",
    "calculate_similarity",
    "Timer",
    "safe_json_loads",
    "create_error_response",
]