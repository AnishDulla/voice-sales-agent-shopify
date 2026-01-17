"""Cartesia TTS service for shared usage across the application."""

import asyncio
import base64
import io
from typing import Optional, Dict, Any
from dataclasses import dataclass

from shared import get_logger
from infrastructure.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class TTSRequest:
    """TTS generation request."""
    text: str
    voice_id: Optional[str] = None
    model: Optional[str] = None
    speed: Optional[float] = None
    format: str = "mp3"  # mp3, wav, etc.


@dataclass 
class TTSResponse:
    """TTS generation response."""
    success: bool
    audio_data: Optional[bytes] = None
    audio_base64: Optional[str] = None
    format: str = "mp3"
    error: Optional[str] = None
    provider: str = "cartesia"
    duration_ms: Optional[float] = None


class CartesiaTTSService:
    """Shared Cartesia TTS service."""
    
    def __init__(self):
        self.api_key = settings.cartesia_api_key
        self.model = settings.cartesia_model
        self.voice_id = settings.cartesia_voice_id
        self.speed = settings.cartesia_speed
        self.language = settings.cartesia_language
        self.available = bool(self.api_key)
        
        if self.available:
            logger.info(f"Cartesia TTS Service initialized with model: {self.model}, voice: {self.voice_id}")
        else:
            logger.warning("Cartesia TTS Service not available - missing API key")
    
    async def generate_speech(self, request: TTSRequest) -> TTSResponse:
        """Generate speech from text using Cartesia TTS."""
        if not self.available:
            return TTSResponse(
                success=False,
                error="Cartesia TTS not available - missing API key",
                provider="cartesia"
            )
        
        import time
        start_time = time.time()
        
        try:
            # Use direct Cartesia API for TTS generation
            logger.info(f"🎵 Cartesia TTS Request:")
            logger.info(f"📝 Text: '{request.text[:100]}{'...' if len(request.text) > 100 else ''}'")
            logger.info(f"🎤 Voice ID: {request.voice_id or self.voice_id}")
            logger.info(f"🔧 Model: {request.model or self.model}")
            logger.info(f"⚡ Speed: {request.speed or self.speed}")
            logger.info(f"🎵 Format: {request.format}")
            
            # Use direct API call (bypass LiveKit plugin for now due to env var issues)
            audio_data = await self._generate_with_direct_api(request.text)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Convert to base64 for JSON transport
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            logger.info(f"Cartesia TTS generated {len(audio_data)} bytes in {duration_ms:.1f}ms")
            
            return TTSResponse(
                success=True,
                audio_data=audio_data,
                audio_base64=audio_base64,
                format=request.format,
                provider="cartesia",
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Cartesia TTS generation failed after {duration_ms:.1f}ms: {e}")
            
            return TTSResponse(
                success=False,
                error=f"TTS generation failed: {str(e)}",
                provider="cartesia",
                duration_ms=duration_ms
            )
    
    async def _generate_with_livekit_plugin(self, tts_instance, text: str) -> bytes:
        """Generate audio using LiveKit Cartesia plugin."""
        # This is a simplified implementation
        # In practice, you'd need to properly handle the LiveKit streaming interface
        
        try:
            # Use direct HTTP approach to Cartesia API since LiveKit plugin has environment variable issues
            logger.info("🔄 Using direct API approach due to LiveKit plugin configuration issues")
            return await self._generate_with_direct_api(text)
            
        except Exception as e:
            logger.error(f"LiveKit plugin generation failed: {e}")
            raise
    
    async def _generate_with_direct_api(self, text: str) -> bytes:
        """Generate audio using direct Cartesia API call."""
        import httpx
        
        logger.info("🌐 Using Direct Cartesia API (fallback from LiveKit plugin)")
        
        url = "https://api.cartesia.ai/tts/bytes"
        
        headers = {
            "Cartesia-Version": "2024-06-30",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "model_id": self.model,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.voice_id
            },
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": 22050
            },
            "language": self.language or "en",
            "speed": self.speed or 1.0
        }
        
        logger.info(f"📡 API Request to {url}")
        logger.info(f"🎤 Voice ID: {self.voice_id}")
        logger.info(f"🔧 Model: {self.model}")
        logger.info(f"⚡ Speed: {self.speed}")
        logger.info(f"🌍 Language: {self.language or 'en'}")
        logger.info(f"🎵 Output Format: WAV PCM S16LE @ 22kHz")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info("🚀 Sending request to Cartesia API...")
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            # The response should be raw audio data
            audio_data = response.content
            logger.info(f"✅ Received {len(audio_data)} bytes of audio data from Cartesia")
            
            # Convert to a more web-friendly format (MP3) if needed
            # For now, return raw PCM data (frontend will handle playback)
            return audio_data
    
    def is_available(self) -> bool:
        """Check if Cartesia TTS is available."""
        return self.available
    
    def get_config(self) -> Dict[str, Any]:
        """Get current TTS configuration."""
        return {
            "provider": "cartesia",
            "model": self.model,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "language": self.language,
            "available": self.available
        }


class BrowserTTSFallbackService:
    """Fallback service that instructs frontend to use browser TTS."""
    
    async def generate_speech(self, request: TTSRequest) -> TTSResponse:
        """Return response indicating frontend should use browser TTS."""
        logger.info(f"Using browser TTS fallback for: '{request.text[:50]}...'")
        
        return TTSResponse(
            success=True,
            audio_data=None,  # No audio data - frontend will use browser TTS
            audio_base64=None,
            format="browser_fallback",
            provider="browser_speechsynthesis"
        )
    
    def is_available(self) -> bool:
        """Browser TTS is always available as fallback."""
        return True
    
    def get_config(self) -> Dict[str, Any]:
        """Get browser TTS configuration."""
        return {
            "provider": "browser_speechsynthesis", 
            "available": True,
            "fallback": True
        }


# Singleton TTS service instance
_tts_service: Optional[Any] = None

def get_tts_service():
    """Get the configured TTS service (Cartesia or fallback)."""
    global _tts_service
    
    if _tts_service is None:
        cartesia_service = CartesiaTTSService()
        
        if cartesia_service.is_available():
            _tts_service = cartesia_service
            logger.info("Using Cartesia TTS service")
        else:
            _tts_service = BrowserTTSFallbackService()
            logger.warning("Using browser TTS fallback service")
    
    return _tts_service


# Convenience function for easy usage
async def generate_tts(
    text: str,
    voice_id: Optional[str] = None,
    model: Optional[str] = None,
    speed: Optional[float] = None,
    format: str = "mp3"
) -> TTSResponse:
    """Generate TTS audio for the given text."""
    service = get_tts_service()
    request = TTSRequest(
        text=text,
        voice_id=voice_id,
        model=model,
        speed=speed,
        format=format
    )
    
    return await service.generate_speech(request)