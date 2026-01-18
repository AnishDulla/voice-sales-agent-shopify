"""Retell AI client integration."""

import httpx
from typing import Dict, Any, Optional, List
import logging
from config import get_settings


logger = logging.getLogger(__name__)


class RetellClient:
    """Client for Retell AI API integration."""
    
    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.retell_api_key
        self.base_url = "https://api.retell.ai"
        
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def register_tools(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Register custom tools with Retell."""
        response = await self.client.post(
            f"{self.base_url}/tools",
            json={"tools": tools}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_agent(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a Retell agent configuration."""
        response = await self.client.post(
            f"{self.base_url}/agents",
            json=config
        )
        response.raise_for_status()
        return response.json()
    
    async def handle_tool_call(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        call_id: str
    ) -> Dict[str, Any]:
        """Handle a tool call from Retell and return the response."""
        logger.info(f"Handling Retell tool call: {tool_name} with params: {parameters}")
        
        return {
            "call_id": call_id,
            "tool_name": tool_name,
            "success": True,
            "result": {}
        }