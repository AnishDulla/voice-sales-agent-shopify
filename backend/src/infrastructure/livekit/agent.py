"""LiveKit voice agent implementation."""

import asyncio
from typing import Optional, Dict, Any

try:
    from livekit import agents, rtc
    from livekit.agents import JobContext, WorkerOptions, cli
    from livekit.plugins import openai, silero
    LIVEKIT_AVAILABLE = True
except ImportError:
    LIVEKIT_AVAILABLE = False
    # Mock classes for when LiveKit is not available
    class JobContext:
        pass
    class WorkerOptions:
        pass

from shared import get_logger, ConversationContext
from orchestration.agent.graph import VoiceAgent
from infrastructure.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class LiveKitVoiceAgent:
    """LiveKit-based voice agent."""
    
    def __init__(self):
        self.agent = VoiceAgent()
        self.vad = silero.VAD.load()
        self.stt = openai.STT()
        self.tts = openai.TTS(voice=settings.tts_voice)
        self.sessions: Dict[str, ConversationContext] = {}
        self.assistants: Dict[str, Any] = {}  # Store assistant instances per session
    
    async def entrypoint(self, ctx: JobContext):
        """Main entrypoint for LiveKit agent."""
        logger.info(f"Starting voice agent for room {ctx.room.name}")
        
        # Initialize session
        session_id = ctx.room.name
        context = ConversationContext(session_id=session_id)
        self.sessions[session_id] = context
        
        # Set up voice pipeline
        initial_ctx = agents.llm.ChatContext().append(
            role="system",
            text="You are a helpful voice sales assistant. Help customers find products and answer their questions."
        )
        
        assistant = agents.VoiceAssistant(
            vad=self.vad,
            stt=self.stt,
            llm=openai.LLM(model=settings.openai_model),
            tts=self.tts,
            chat_ctx=initial_ctx,
            allow_interruptions=True,
            interrupt_speech_duration=0.5,
        )
        
        # Store assistant reference for interruption control
        self.assistants[session_id] = assistant
        
        # Handle participant events
        @ctx.room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant connected: {participant.identity}")
            asyncio.create_task(
                assistant.say(
                    "Hello! Welcome to our store. I'm here to help you find products. What are you looking for today?",
                    allow_interruptions=True
                )
            )
        
        # Set up function calling for tools
        async def handle_function(name: str, args: Dict[str, Any]) -> Any:
            """Handle function calls from the LLM."""
            from orchestration.tools.registry import registry
            
            logger.info(f"Handling function call: {name} with args: {args}")
            
            try:
                tool = registry.get(name)
                result = await tool.execute(**args)
                
                if result.success:
                    return result.data
                else:
                    logger.error(f"Tool execution failed: {result.error}")
                    return {"error": result.error}
                    
            except Exception as e:
                logger.error(f"Function call failed: {e}")
                return {"error": str(e)}
        
        # Register available functions
        assistant.llm.register_function("search_products", handle_function)
        assistant.llm.register_function("get_product_details", handle_function)
        assistant.llm.register_function("check_inventory", handle_function)
        
        # Start the assistant
        assistant.start(ctx.room)
        
        # Handle room events
        @ctx.room.on("track_published")
        def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            if publication.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Audio track published by {participant.identity}")
        
        @ctx.room.on("participant_disconnected")
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant disconnected: {participant.identity}")
            # Clean up assistant reference when participant disconnects
            if session_id in self.assistants:
                del self.assistants[session_id]
        
        # Keep the agent running
        await asyncio.sleep(float('inf'))
    
    async def interrupt_speech(self, session_id: str) -> bool:
        """Interrupt ongoing speech for a session."""
        if session_id in self.assistants:
            try:
                assistant = self.assistants[session_id]
                # Call interrupt method if available
                if hasattr(assistant, 'interrupt'):
                    await assistant.interrupt()
                    logger.info(f"Successfully interrupted speech for session {session_id}")
                    return True
                else:
                    logger.warning("Assistant does not support interrupt method")
                    return False
            except Exception as e:
                logger.error(f"Failed to interrupt speech for session {session_id}: {e}")
                return False
        else:
            logger.warning(f"No assistant found for session {session_id}")
            return False


def create_worker():
    """Create LiveKit worker."""
    if not LIVEKIT_AVAILABLE:
        raise ImportError("LiveKit is not available. Install with: pip install livekit livekit-agents")
    
    agent = LiveKitVoiceAgent()
    
    worker_options = WorkerOptions(
        entrypoint_fnc=agent.entrypoint,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
        ws_url=settings.livekit_url,
    )
    
    return worker_options


def run_agent():
    """Run the LiveKit agent."""
    if not LIVEKIT_AVAILABLE:
        logger.error("LiveKit is not available. Install with: pip install livekit livekit-agents livekit-plugins-openai livekit-plugins-silero")
        return
    
    cli.run_app(create_worker())