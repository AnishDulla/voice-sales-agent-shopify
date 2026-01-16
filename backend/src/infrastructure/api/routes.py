"""API routes."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from typing import Dict, Any, Optional
import json
import uuid

from shared import (
    ConversationContext,
    generate_session_id,
    get_logger,
    create_error_response
)
from infrastructure.config.settings import get_settings
from orchestration.agent.graph import VoiceAgent
from infrastructure.livekit.agent import LiveKitVoiceAgent

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter()

# In-memory session storage (replace with Redis in production)
sessions: Dict[str, ConversationContext] = {}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.app_env
    }


@router.get("/config")
async def get_config():
    """Get public configuration."""
    return {
        "features": {
            "voice": settings.enable_voice,
            "chat": settings.enable_chat,
            "analytics": settings.enable_analytics,
            "recommendations": settings.enable_recommendations
        },
        "voice": {
            "enabled": settings.enable_voice,
            "language": settings.stt_language
        }
    }


@router.post("/api/sessions")
async def create_session(
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Create a new conversation session."""
    session_id = generate_session_id()
    
    context = ConversationContext(
        session_id=session_id,
        user_preferences=metadata or {}
    )
    
    sessions[session_id] = context
    
    logger.info(f"Created session: {session_id}")
    
    return {
        "session_id": session_id,
        "token": session_id,  # In production, generate JWT
        "expires_in": settings.session_ttl
    }


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    context = sessions[session_id]
    
    return {
        "session_id": session_id,
        "messages": [msg.dict() for msg in context.messages],
        "context": {
            "cart_items": context.cart_items,
            "viewed_products": context.viewed_products,
            "user_preferences": context.user_preferences
        }
    }


@router.delete("/api/sessions/{session_id}")
async def end_session(session_id: str):
    """End a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del sessions[session_id]
    
    logger.info(f"Ended session: {session_id}")
    
    return {"message": "Session ended successfully"}


from pydantic import BaseModel

class SearchProductsRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 10

@router.post("/api/products/search")
async def search_products(request: SearchProductsRequest):
    """Search products endpoint for testing."""
    from orchestration.tools.registry import registry
    
    try:
        tool = registry.get("search_products")
        result = await tool.execute(
            query=request.query,
            limit=request.limit,
            **(request.filters or {})
        )
        
        if result.success:
            return {
                "products": result.data,
                "count": len(result.data) if result.data else 0
            }
        else:
            raise HTTPException(status_code=400, detail=result.error)
            
    except Exception as e:
        logger.error(f"Product search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/voice/session")
async def voice_session(websocket: WebSocket):
    """WebSocket endpoint for voice sessions."""
    await websocket.accept()
    
    session_id = None
    agent = None
    context = None
    
    try:
        # Wait for session start message
        data = await websocket.receive_json()
        
        if data.get("type") != "session.start":
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Expected session.start message"}
            })
            return
        
        session_id = data["data"].get("session_id") or generate_session_id()
        
        # Get or create context
        if session_id in sessions:
            context = sessions[session_id]
        else:
            context = ConversationContext(session_id=session_id)
            sessions[session_id] = context
        
        # Create agent
        agent = VoiceAgent()
        
        # Send ready message
        await websocket.send_json({
            "type": "session.ready",
            "data": {
                "session_id": session_id,
                "message": "Session ready"
            }
        })
        
        # Handle messages
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "text.input":
                # Process text message
                text = data["data"].get("text", "")
                
                logger.info(f"Processing text input: {text[:100]}")
                
                # Process with agent
                response = await agent.process_message(
                    message=text,
                    session_id=session_id,
                    context=context
                )
                
                # Send response
                await websocket.send_json({
                    "type": "agent.response",
                    "data": {
                        "text": response,
                        "intent": "product_search"  # Would come from agent
                    }
                })
                
            elif message_type == "audio.input":
                # Handle audio input (simplified)
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Audio processing not yet implemented"}
                })
                
            elif message_type == "session.end":
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
    finally:
        if session_id and session_id in sessions:
            # Keep session for a while after disconnect
            pass


from pydantic import BaseModel

class ToolExecutionRequest(BaseModel):
    tool: str
    parameters: Dict[str, Any]

@router.post("/api/test/tool-execution")
async def test_tool_execution(request: ToolExecutionRequest):
    """Test endpoint for tool execution."""
    from orchestration.tools.registry import registry
    
    try:
        tool_instance = registry.get(request.tool)
        result = await tool_instance.execute(**request.parameters)
        
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata
        }
    except Exception as e:
        logger.error(f"Tool execution test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))