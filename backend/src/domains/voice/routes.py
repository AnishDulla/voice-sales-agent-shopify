"""Voice domain routes for Retell AI integration."""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from pydantic import BaseModel
import logging

from domains.voice.agent.optimized_agent import VoiceAgentHandler
from domains.voice.tools.registry import ToolRegistry
from integrations.retell.client import RetellClient


router = APIRouter()
logger = logging.getLogger(__name__)


class RetellToolCall(BaseModel):
    """Retell tool call request."""
    tool_name: str
    parameters: Dict[str, Any]
    call_id: str


class RetellWebhookRequest(BaseModel):
    """Retell webhook request."""
    event: str
    data: Dict[str, Any]


@router.post("/retell/tools")
async def handle_retell_tool_call(request: RetellToolCall):
    """Handle tool calls from Retell AI."""
    try:
        from app import shopify_client
        handler = VoiceAgentHandler(shopify_client)
        result = await handler.execute_tool(
            tool_name=request.tool_name,
            parameters=request.parameters
        )
        
        return {
            "call_id": request.call_id,
            "success": result.get("success", True),
            "result": result
        }
    except Exception as e:
        logger.error(f"Tool call failed: {e}")
        return {
            "call_id": request.call_id,
            "success": False,
            "error": str(e)
        }


@router.post("/retell/webhook")
async def handle_retell_webhook(request: RetellWebhookRequest):
    """Handle webhooks from Retell AI."""
    event = request.event
    data = request.data
    
    logger.info(f"Received Retell webhook: {event}")
    
    if event == "call.started":
        return {"status": "acknowledged", "session_id": data.get("call_id")}
    elif event == "call.ended":
        return {"status": "acknowledged"}
    elif event == "tool.called":
        tool_name = data.get("tool_name")
        parameters = data.get("parameters", {})
        call_id = data.get("call_id")
        
        from app import shopify_client
        handler = VoiceAgentHandler(shopify_client)
        result = await handler.execute_tool(tool_name, parameters)
        
        return {
            "call_id": call_id,
            "result": result
        }
    else:
        return {"status": "ignored"}


@router.get("/retell/tools/list")
async def list_available_tools():
    """List all available tools for Retell configuration."""
    registry = ToolRegistry()
    tools = registry.get_tool_definitions()
    
    return {
        "tools": tools,
        "count": len(tools)
    }


@router.post("/retell/agent/configure")
async def configure_retell_agent(
    agent_prompt: str = "You are a helpful voice commerce assistant.",
    voice: str = "sarah",
    language: str = "en-US"
):
    """Configure the Retell agent with our tools."""
    try:
        retell_client = RetellClient()
        registry = ToolRegistry()
        
        tools = registry.get_tool_definitions()
        
        config = {
            "prompt": agent_prompt,
            "voice": voice,
            "language": language,
            "tools": tools,
            "webhook_url": "https://your-domain.com/api/voice/retell/webhook"
        }
        
        result = await retell_client.create_agent(config)
        
        return {
            "success": True,
            "agent_id": result.get("agent_id"),
            "configuration": config
        }
    except Exception as e:
        logger.error(f"Failed to configure Retell agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))