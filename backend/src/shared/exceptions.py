"""Custom exceptions for the voice sales agent."""

from typing import Optional, Dict, Any


class VoiceAgentException(Exception):
    """Base exception for all voice agent errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ToolExecutionError(VoiceAgentException):
    """Raised when a tool fails to execute."""
    
    def __init__(
        self,
        tool_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Tool '{tool_name}' failed: {message}",
            error_code="TOOL_EXECUTION_ERROR",
            details={"tool_name": tool_name, **(details or {})}
        )
        self.tool_name = tool_name


class ToolNotFoundError(VoiceAgentException):
    """Raised when a requested tool doesn't exist."""
    
    def __init__(self, tool_name: str):
        super().__init__(
            message=f"Tool '{tool_name}' not found in registry",
            error_code="TOOL_NOT_FOUND",
            details={"tool_name": tool_name}
        )
        self.tool_name = tool_name


class ShopifyAPIError(VoiceAgentException):
    """Raised when Shopify API call fails."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Shopify API error: {message}",
            error_code="SHOPIFY_API_ERROR",
            details={"status_code": status_code, "response": response}
        )
        self.status_code = status_code
        self.response = response


class VoiceProcessingError(VoiceAgentException):
    """Raised when voice processing fails."""
    
    def __init__(
        self,
        stage: str,  # "transcription", "synthesis", "vad"
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Voice processing error in {stage}: {message}",
            error_code="VOICE_PROCESSING_ERROR",
            details={"stage": stage, **(details or {})}
        )
        self.stage = stage


class SessionError(VoiceAgentException):
    """Raised when session management fails."""
    
    def __init__(
        self,
        session_id: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Session error for {session_id}: {message}",
            error_code="SESSION_ERROR",
            details={"session_id": session_id, **(details or {})}
        )
        self.session_id = session_id


class ConfigurationError(VoiceAgentException):
    """Raised when configuration is invalid."""
    
    def __init__(
        self,
        config_key: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Configuration error for '{config_key}': {message}",
            error_code="CONFIGURATION_ERROR",
            details={"config_key": config_key, **(details or {})}
        )
        self.config_key = config_key


class RateLimitError(VoiceAgentException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        resource: str,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        message = f"Rate limit exceeded for {resource}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"resource": resource, "retry_after": retry_after, **(details or {})}
        )
        self.resource = resource
        self.retry_after = retry_after


class ValidationError(VoiceAgentException):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        field: str,
        message: str,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Validation error for '{field}': {message}",
            error_code="VALIDATION_ERROR",
            details={"field": field, "value": value, **(details or {})}
        )
        self.field = field
        self.value = value