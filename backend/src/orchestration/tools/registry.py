"""Tool registry for dynamic tool management."""

from typing import Dict, List, Optional, Type, Any
from functools import wraps

from .base import BaseTool, ToolDefinition
from shared import ToolNotFoundError, get_logger


logger = get_logger(__name__)


class ToolRegistry:
    """Registry for managing available tools."""
    
    _instance: Optional["ToolRegistry"] = None
    _tools: Dict[str, BaseTool] = {}
    
    def __new__(cls) -> "ToolRegistry":
        """Singleton pattern for global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(self, tool: BaseTool, override: bool = False) -> None:
        """Register a tool in the registry."""
        if tool.name in self._tools and not override:
            logger.warning(f"Tool '{tool.name}' already registered, skipping")
            return
        
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, tool_name: str) -> None:
        """Remove a tool from the registry."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
    
    def get(self, tool_name: str) -> BaseTool:
        """Get a tool by name."""
        if tool_name not in self._tools:
            raise ToolNotFoundError(tool_name)
        return self._tools[tool_name]
    
    def get_all(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return self._tools.copy()
    
    def get_by_category(self, category: str) -> List[BaseTool]:
        """Get tools by category."""
        return [
            tool for tool in self._tools.values()
            if tool.category == category
        ]
    
    def get_definitions(self) -> List[ToolDefinition]:
        """Get definitions for all tools."""
        return [tool.get_definition() for tool in self._tools.values()]
    
    def exists(self, tool_name: str) -> bool:
        """Check if a tool exists."""
        return tool_name in self._tools
    
    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.info("Cleared tool registry")
    
    def get_categories(self) -> List[str]:
        """Get unique tool categories."""
        return list(set(tool.category for tool in self._tools.values()))
    
    async def execute_tool(
        self,
        tool_name: str,
        **kwargs
    ) -> Any:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        return await tool.execute_with_logging(**kwargs)
    
    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)
    
    def __contains__(self, tool_name: str) -> bool:
        """Check if tool exists using 'in' operator."""
        return tool_name in self._tools
    
    def __repr__(self) -> str:
        tool_names = ", ".join(self._tools.keys())
        return f"ToolRegistry({len(self._tools)} tools: {tool_names})"


# Global registry instance
registry = ToolRegistry()


def register_tool(
    name: Optional[str] = None,
    category: str = "general",
    description: Optional[str] = None
):
    """Decorator to register a tool class."""
    def decorator(cls: Type[BaseTool]) -> Type[BaseTool]:
        # Create instance and set properties
        instance = cls()
        
        if name:
            instance.name = name
        if description:
            instance.description = description
        instance.category = category
        
        # Register the instance
        registry.register(instance)
        
        # Return the original class
        return cls
    
    return decorator


def discover_tools(module_path: str) -> None:
    """Discover and register tools from a module."""
    import importlib
    import pkgutil
    
    module = importlib.import_module(module_path)
    
    # Iterate through submodules
    for importer, modname, ispkg in pkgutil.iter_modules(module.__path__):
        full_module_name = f"{module_path}.{modname}"
        
        # Skip base and registry modules
        if modname in ["base", "registry"]:
            continue
        
        try:
            submodule = importlib.import_module(full_module_name)
            
            # Look for tool classes
            for attr_name in dir(submodule):
                attr = getattr(submodule, attr_name)
                
                # Check if it's a tool class
                if (
                    isinstance(attr, type) and
                    issubclass(attr, BaseTool) and
                    attr != BaseTool and
                    not attr_name.startswith("_")
                ):
                    # Create and register instance
                    try:
                        tool_instance = attr()
                        registry.register(tool_instance)
                    except Exception as e:
                        logger.error(f"Failed to register tool {attr_name}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to import module {full_module_name}: {e}")


class ToolSelector:
    """Select appropriate tools based on intent."""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
    
    def select_by_keywords(self, text: str) -> List[BaseTool]:
        """Select tools based on keywords in text."""
        selected = []
        text_lower = text.lower()
        
        for tool in self.registry.get_all().values():
            # Check if tool keywords appear in text
            tool_keywords = tool.description.lower().split()
            if any(keyword in text_lower for keyword in tool_keywords):
                selected.append(tool)
        
        return selected
    
    def select_by_intent(self, intent: str) -> List[BaseTool]:
        """Select tools based on intent."""
        intent_tool_mapping = {
            "product_search": ["search_products", "get_product_details"],
            "add_to_cart": ["add_to_cart", "validate_inventory"],
            "checkout": ["get_cart_summary", "calculate_shipping"],
            "sizing": ["get_size_chart", "compare_sizes"],
            "policy": ["get_return_policy", "get_shipping_info"],
        }
        
        tool_names = intent_tool_mapping.get(intent, [])
        tools = []
        
        for name in tool_names:
            if self.registry.exists(name):
                tools.append(self.registry.get(name))
        
        return tools
    
    def rank_tools(self, tools: List[BaseTool], context: Dict[str, Any]) -> List[BaseTool]:
        """Rank tools by relevance to context."""
        # Simple ranking - could be enhanced with ML
        scored_tools = []
        
        for tool in tools:
            score = 0
            
            # Prefer recently used tools
            if "recent_tools" in context:
                if tool.name in context["recent_tools"]:
                    score += 10
            
            # Prefer tools from same category as previous
            if "last_category" in context:
                if tool.category == context["last_category"]:
                    score += 5
            
            scored_tools.append((score, tool))
        
        # Sort by score descending
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        
        return [tool for _, tool in scored_tools]