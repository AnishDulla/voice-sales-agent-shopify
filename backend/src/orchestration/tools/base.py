"""Base tool abstraction for agent capabilities."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field
import inspect
from datetime import datetime

from shared import ToolResult, get_logger, LoggerMixin


T = TypeVar("T", bound="BaseTool")


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    
    name: str
    type: str
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    """Tool definition for agent understanding."""
    
    name: str
    description: str
    category: str
    parameters: List[ToolParameter]
    examples: List[Dict[str, Any]] = Field(default_factory=list)


class BaseTool(ABC, LoggerMixin):
    """Base class for all agent tools."""
    
    name: str = ""
    description: str = ""
    category: str = "general"
    
    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__.replace("Tool", "").lower()
        super().__init__()
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Validate parameters against tool signature."""
        sig = inspect.signature(self.execute)
        required_params = {
            name for name, param in sig.parameters.items()
            if param.default == inspect.Parameter.empty and name != "self"
        }
        
        missing = required_params - set(parameters.keys())
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")
        
        return True
    
    def get_definition(self) -> ToolDefinition:
        """Get tool definition for agent."""
        sig = inspect.signature(self.execute)
        parameters = []
        
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            
            param_type = "string"  # Default type
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"
            
            parameters.append(ToolParameter(
                name=name,
                type=param_type,
                description=f"Parameter {name}",
                required=param.default == inspect.Parameter.empty,
                default=param.default if param.default != inspect.Parameter.empty else None
            ))
        
        return ToolDefinition(
            name=self.name,
            description=self.description,
            category=self.category,
            parameters=parameters
        )
    
    async def execute_with_logging(self, **kwargs) -> ToolResult:
        """Execute tool with automatic logging."""
        start_time = datetime.utcnow()
        
        self.log_event(
            "tool_execution_started",
            tool_name=self.name,
            parameters=kwargs
        )
        
        try:
            self.validate_parameters(kwargs)
            result = await self.execute(**kwargs)
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.log_event(
                "tool_execution_completed",
                tool_name=self.name,
                duration_ms=duration_ms,
                success=result.success
            )
            
            return result
            
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            self.log_error(
                e,
                "tool_execution_failed",
                tool_name=self.name,
                duration_ms=duration_ms
            )
            
            return ToolResult.fail(str(e))
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"
    
    def __repr__(self) -> str:
        return self.__str__()


class CompositeTool(BaseTool):
    """Tool that combines multiple sub-tools."""
    
    def __init__(self, tools: List[BaseTool]):
        super().__init__()
        self.tools = {tool.name: tool for tool in tools}
    
    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a specific sub-tool."""
        if tool_name not in self.tools:
            return ToolResult.fail(f"Sub-tool '{tool_name}' not found")
        
        return await self.tools[tool_name].execute_with_logging(**kwargs)
    
    def get_available_tools(self) -> List[str]:
        """Get list of available sub-tools."""
        return list(self.tools.keys())


class ToolContext:
    """Context passed to tools during execution."""
    
    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.metadata = metadata or {}
        self.execution_history: List[Dict[str, Any]] = []
    
    def add_execution(self, tool_name: str, result: ToolResult) -> None:
        """Add tool execution to history."""
        self.execution_history.append({
            "tool_name": tool_name,
            "timestamp": datetime.utcnow().isoformat(),
            "success": result.success,
            "data": result.data,
            "error": result.error
        })
    
    def get_last_result(self, tool_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get last execution result, optionally filtered by tool name."""
        if not self.execution_history:
            return None
        
        if tool_name:
            for execution in reversed(self.execution_history):
                if execution["tool_name"] == tool_name:
                    return execution
            return None
        
        return self.execution_history[-1]