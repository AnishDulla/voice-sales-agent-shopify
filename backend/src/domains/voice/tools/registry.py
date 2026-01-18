"""Tool registry for Retell AI integration."""

from typing import Dict, Any, List, Optional


class ToolRegistry:
    """Registry of available tools for the voice agent."""
    
    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """Get all tool definitions for Retell AI configuration."""
        return [
            {
                "name": "get_product_catalog",
                "description": "Get a catalog of all available products",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of products to return",
                            "default": 50
                        }
                    }
                }
            },
            {
                "name": "get_product_details",
                "description": "Get detailed information about a specific product",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "The ID of the product"
                        }
                    },
                    "required": ["product_id"]
                }
            },
            {
                "name": "check_inventory",
                "description": "Check if a product is available in the requested quantity",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "The ID of the product"
                        },
                        "variant_id": {
                            "type": "string",
                            "description": "The ID of the specific variant (optional)"
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "The desired quantity",
                            "default": 1
                        }
                    },
                    "required": ["product_id"]
                }
            },
            {
                "name": "search_products",
                "description": "Search for products by keyword",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "create_cart",
                "description": "Create a new shopping cart",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "description": "Initial cart items",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "variant_id": {
                                        "type": "string",
                                        "description": "Variant ID"
                                    },
                                    "quantity": {
                                        "type": "integer",
                                        "description": "Quantity"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            {
                "name": "update_cart",
                "description": "Update an existing shopping cart",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cart_id": {
                            "type": "string",
                            "description": "Cart ID"
                        },
                        "items": {
                            "type": "array",
                            "description": "Updated cart items",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "variant_id": {
                                        "type": "string",
                                        "description": "Variant ID"
                                    },
                                    "quantity": {
                                        "type": "integer",
                                        "description": "Quantity"
                                    }
                                }
                            }
                        }
                    },
                    "required": ["cart_id", "items"]
                }
            }
        ]
    
    @staticmethod
    def get_tool_by_name(tool_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific tool definition by name."""
        tools = ToolRegistry.get_tool_definitions()
        for tool in tools:
            if tool["name"] == tool_name:
                return tool
        return None