"""Structured logging configuration."""

import sys
import structlog
from typing import Any, Dict, Optional
from datetime import datetime


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = True,
    correlation_id_var: Optional[str] = None
) -> None:
    """Configure structured logging for the application."""
    
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if correlation_id_var:
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[structlog.processors.CallsiteParameter.FUNC_NAME],
                additional_ignores=["logging", "__main__"]
            )
        )
    
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging
    import logging
    
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin to add logging capabilities to classes."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger bound to class name."""
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
    
    def log_event(
        self,
        event: str,
        level: str = "info",
        **kwargs: Any
    ) -> None:
        """Log an event with structured data."""
        log_method = getattr(self.logger, level)
        log_method(event, **kwargs)
    
    def log_error(
        self,
        error: Exception,
        event: str = "error_occurred",
        **kwargs: Any
    ) -> None:
        """Log an error with context."""
        self.logger.error(
            event,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs
        )
    
    def log_timing(
        self,
        event: str,
        duration_ms: float,
        **kwargs: Any
    ) -> None:
        """Log timing information."""
        self.logger.info(
            event,
            duration_ms=duration_ms,
            **kwargs
        )


class RequestLogger:
    """Context manager for request logging."""
    
    def __init__(
        self,
        logger: structlog.BoundLogger,
        request_id: str,
        operation: str
    ):
        self.logger = logger
        self.request_id = request_id
        self.operation = operation
        self.start_time = None
        
    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.logger.info(
            "request_started",
            request_id=self.request_id,
            operation=self.operation
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (datetime.utcnow() - self.start_time).total_seconds() * 1000
        
        if exc_type:
            self.logger.error(
                "request_failed",
                request_id=self.request_id,
                operation=self.operation,
                duration_ms=duration_ms,
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )
        else:
            self.logger.info(
                "request_completed",
                request_id=self.request_id,
                operation=self.operation,
                duration_ms=duration_ms
            )


def log_tool_execution(tool_name: str, parameters: Dict[str, Any]) -> callable:
    """Decorator for logging tool execution."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            logger = get_logger("tools")
            start_time = datetime.utcnow()
            
            logger.info(
                "tool_execution_started",
                tool_name=tool_name,
                parameters=parameters
            )
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                logger.info(
                    "tool_execution_completed",
                    tool_name=tool_name,
                    duration_ms=duration_ms,
                    success=True
                )
                return result
                
            except Exception as e:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                logger.error(
                    "tool_execution_failed",
                    tool_name=tool_name,
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                raise
        
        return wrapper
    return decorator