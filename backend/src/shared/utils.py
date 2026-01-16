"""Utility functions for the voice sales agent."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TypeVar
from functools import wraps
import asyncio


T = TypeVar("T")


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    unique_id = str(uuid.uuid4())
    return f"{prefix}_{unique_id}" if prefix else unique_id


def generate_session_id() -> str:
    """Generate a session ID."""
    return generate_id("session")


def generate_request_id() -> str:
    """Generate a request ID for tracing."""
    return generate_id("req")


def sanitize_text(text: str) -> str:
    """Sanitize text for safe processing."""
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters that might cause issues
    text = re.sub(r'[^\w\s\-.,!?]', '', text)
    return text.strip()




def calculate_cache_key(*args: Any) -> str:
    """Calculate cache key from arguments."""
    key_data = json.dumps(args, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()




def extract_number(text: str) -> Optional[int]:
    """Extract first number from text."""
    match = re.search(r'\d+', text)
    return int(match.group()) if match else None


def format_price(amount: float, currency: str = "USD") -> str:
    """Format price for display."""
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "CAD": "C$",
    }
    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{amount:.2f}"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator for retrying async functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator


def batch_items(items: List[T], batch_size: int) -> List[List[T]]:
    """Split items into batches."""
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result




def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_phone(phone: str) -> bool:
    """Validate phone number format."""
    # Simple validation - digits with optional formatting
    cleaned = re.sub(r'[^\d]', '', phone)
    return len(cleaned) >= 10


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self):
        self.start_time = None
        self.duration = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return self.duration * 1000 if self.duration else 0


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Safely parse JSON with default value."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def create_error_response(
    error: Exception,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create standardized error response."""
    from shared.exceptions import VoiceAgentException
    
    if isinstance(error, VoiceAgentException):
        return {
            "error": {
                "code": error.error_code,
                "message": str(error),
                "details": error.details
            },
            "request_id": request_id
        }
    
    return {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {"type": type(error).__name__}
        },
        "request_id": request_id
    }