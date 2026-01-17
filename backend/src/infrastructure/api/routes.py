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
from orchestration.agent.optimized_agent import OptimizedVoiceAgent

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter()

# In-memory session storage (replace with Redis in production)
sessions: Dict[str, ConversationContext] = {}

# Simple interrupt manager to avoid full LiveKit initialization in WebSocket
class SimpleInterruptManager:
    """Lightweight interrupt manager for WebSocket sessions."""
    
    def __init__(self):
        self.active_sessions: Dict[str, bool] = {}
        self.interrupt_flags: Dict[str, bool] = {}
    
    def register_session(self, session_id: str):
        """Register a session for interrupt tracking."""
        self.active_sessions[session_id] = True
        self.interrupt_flags[session_id] = False
        
    def interrupt_session(self, session_id: str) -> bool:
        """Flag a session for interruption."""
        if session_id in self.active_sessions:
            self.interrupt_flags[session_id] = True
            logger.info(f"Interrupt flag set for session {session_id}")
            return True
        return False
    
    def is_interrupted(self, session_id: str) -> bool:
        """Check if session has been interrupted."""
        return self.interrupt_flags.get(session_id, False)
    
    def clear_interrupt(self, session_id: str):
        """Clear interrupt flag for session."""
        if session_id in self.interrupt_flags:
            self.interrupt_flags[session_id] = False
    
    def cleanup_session(self, session_id: str):
        """Clean up session interrupt tracking."""
        self.active_sessions.pop(session_id, None)
        self.interrupt_flags.pop(session_id, None)

interrupt_manager = SimpleInterruptManager()


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
        
        # Create optimized agent with streaming
        agent = OptimizedVoiceAgent()  # Ultra-optimized agent
        interrupt_manager.register_session(session_id)
        
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
                
                # Import TTS service
                from infrastructure.tts.cartesia_service import generate_tts
                
                # Process with streaming agent
                full_response = ""
                chunk_count = 0
                
                async for chunk in agent.process_message_streaming(
                    message=text,
                    session_id=session_id,
                    context=context
                ):
                    if chunk["type"] == "text_chunk" and chunk.get("trigger_tts"):
                        chunk_count += 1
                        sentence = chunk["content"]
                        
                        # Log chunk generation
                        logger.info(f"📝 Chunk {chunk_count}: '{sentence[:50]}...'")
                        
                        # Send text chunk immediately
                        await websocket.send_json({
                            "type": "text.chunk",
                            "data": {
                                "text": sentence,
                                "chunk_id": chunk_count
                            }
                        })
                        
                        # Generate TTS for this chunk immediately
                        try:
                            logger.info(f"🎵 Generating TTS for chunk {chunk_count}")
                            tts_response = await generate_tts(
                                text=sentence,
                                format="wav"
                            )
                            
                            if tts_response.success:
                                logger.info(f"✅ TTS chunk {chunk_count} ready in {tts_response.duration_ms:.1f}ms")
                                
                                # Send audio chunk immediately
                                await websocket.send_json({
                                    "type": "audio.chunk",
                                    "data": {
                                        "audio_base64": tts_response.audio_base64,
                                        "format": tts_response.format,
                                        "chunk_id": chunk_count,
                                        "text": sentence
                                    }
                                })
                            else:
                                logger.error(f"TTS chunk {chunk_count} failed: {tts_response.error}")
                                
                        except Exception as e:
                            logger.error(f"TTS generation error for chunk {chunk_count}: {e}")
                            
                    elif chunk["type"] == "completion":
                        full_response = chunk["full_response"]
                        
                        # Send final response summary
                        await websocket.send_json({
                            "type": "agent.response",
                            "data": {
                                "text": full_response,
                                "chunks_sent": chunk_count
                            }
                        })
                        
                        logger.info(f"✨ Response complete: {chunk_count} chunks sent")
                
            elif message_type == "audio.input":
                # Handle audio input (simplified)
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "Audio processing not yet implemented"}
                })
                
            elif message_type == "interrupt.speech":
                # Handle speech interruption request
                logger.info(f"Speech interruption requested for session {session_id}")
                
                # Flag session for interruption
                interrupted = interrupt_manager.interrupt_session(session_id)
                
                await websocket.send_json({
                    "type": "speech.interrupted",
                    "data": {
                        "success": interrupted,
                        "message": "Speech interrupted" if interrupted else "Failed to interrupt speech"
                    }
                })
                
            elif message_type == "user.speaking":
                # Handle user speaking detection (VAD trigger)
                transcript = data["data"].get("transcript", "")
                interrupted_tts = data["data"].get("interrupted_tts", False)
                
                logger.info(f"User speaking detected for session {session_id}: '{transcript[:50]}...'")
                
                # Automatically flag for TTS interruption when user starts speaking
                interrupted = interrupt_manager.interrupt_session(session_id)
                
                await websocket.send_json({
                    "type": "speech.interrupted", 
                    "data": {
                        "success": interrupted,
                        "message": "User speaking, interrupting TTS" if interrupted else "TTS interruption failed",
                        "interrupted_tts": interrupted_tts
                    }
                })
                
            elif message_type == "tts.started":
                # Handle TTS started notification from frontend
                text = data["data"].get("text", "")
                logger.info(f"Frontend TTS started for session {session_id}: '{text[:50]}...'")
                
                # Clear any previous interrupt flags when TTS starts
                interrupt_manager.clear_interrupt(session_id)
                
                # Optionally, you could store TTS state here for coordination
                await websocket.send_json({
                    "type": "tts.acknowledged",
                    "data": {"message": "TTS start acknowledged"}
                })
                
            elif message_type == "tts.ended":
                # Handle TTS ended notification from frontend
                text = data["data"].get("text", "")
                logger.info(f"Frontend TTS ended for session {session_id}: '{text[:50]}...'")
                
                # TTS ended, ready for new input
                await websocket.send_json({
                    "type": "tts.acknowledged", 
                    "data": {"message": "TTS end acknowledged"}
                })
                
            elif message_type == "tts.generate":
                # Handle TTS generation request from frontend
                from infrastructure.tts.cartesia_service import generate_tts
                
                text = data["data"].get("text", "")
                voice_id = data["data"].get("voice_id")
                model = data["data"].get("model")
                speed = data["data"].get("speed")
                format_type = data["data"].get("format", "mp3")
                
                logger.info(f"🎵 TTS Generation Request - Session: {session_id}")
                logger.info(f"📝 Text: '{text[:100]}{'...' if len(text) > 100 else ''}'")
                logger.info(f"🎤 Voice: {voice_id or 'default'}, Model: {model or 'default'}, Speed: {speed or 'default'}")
                
                try:
                    # Generate TTS using Cartesia service
                    logger.info("🚀 Calling Cartesia TTS service...")
                    tts_response = await generate_tts(
                        text=text,
                        voice_id=voice_id,
                        model=model,
                        speed=speed,
                        format=format_type
                    )
                    
                    logger.info(f"✅ TTS Generation Complete - Provider: {tts_response.provider}, Success: {tts_response.success}")
                    
                    if tts_response.success:
                        logger.info(f"TTS generated successfully with {tts_response.provider} in {tts_response.duration_ms:.1f}ms")
                        
                        await websocket.send_json({
                            "type": "tts.generated",
                            "data": {
                                "success": True,
                                "audio_base64": tts_response.audio_base64,
                                "format": tts_response.format,
                                "provider": tts_response.provider,
                                "duration_ms": tts_response.duration_ms,
                                "text": text
                            }
                        })
                    else:
                        logger.error(f"TTS generation failed: {tts_response.error}")
                        
                        await websocket.send_json({
                            "type": "tts.generated",
                            "data": {
                                "success": False,
                                "error": tts_response.error,
                                "provider": tts_response.provider,
                                "text": text
                            }
                        })
                        
                except Exception as e:
                    logger.error(f"TTS generation error: {e}")
                    
                    await websocket.send_json({
                        "type": "tts.generated",
                        "data": {
                            "success": False,
                            "error": f"TTS generation failed: {str(e)}",
                            "provider": "unknown",
                            "text": text
                        }
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
        if session_id:
            # Clean up interrupt tracking
            interrupt_manager.cleanup_session(session_id)
            # Keep session for a while after disconnect
            if session_id in sessions:
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