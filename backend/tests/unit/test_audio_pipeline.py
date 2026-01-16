"""Test complete audio pipeline with TTS interruption."""

import pytest
from unittest.mock import Mock, AsyncMock
import json

from infrastructure.api.routes import SimpleInterruptManager


class TestAudioPipelineFlow:
    """Test the complete audio pipeline flow."""

    @pytest.fixture
    def interrupt_manager(self):
        """Create a fresh interrupt manager."""
        return SimpleInterruptManager()

    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket for testing."""
        websocket = Mock()
        websocket.send_json = AsyncMock()
        return websocket

    def test_complete_conversation_flow(self, interrupt_manager):
        """Test a complete conversation flow with TTS interruption."""
        session_id = "test_session"
        
        # 1. Session starts
        interrupt_manager.register_session(session_id)
        assert session_id in interrupt_manager.active_sessions
        
        # 2. User asks question (normal flow)
        assert not interrupt_manager.is_interrupted(session_id)
        
        # 3. Bot starts speaking (TTS)
        # Frontend would send tts.started, backend clears interrupt flag
        interrupt_manager.clear_interrupt(session_id)
        assert not interrupt_manager.is_interrupted(session_id)
        
        # 4. User starts speaking during TTS (interruption)
        interrupted = interrupt_manager.interrupt_session(session_id)
        assert interrupted is True
        assert interrupt_manager.is_interrupted(session_id)
        
        # 5. Frontend stops TTS, backend processes new input
        interrupt_manager.clear_interrupt(session_id)
        assert not interrupt_manager.is_interrupted(session_id)
        
        # 6. Session cleanup
        interrupt_manager.cleanup_session(session_id)
        assert session_id not in interrupt_manager.active_sessions

    @pytest.mark.asyncio
    async def test_websocket_message_flow(self, interrupt_manager, mock_websocket):
        """Test WebSocket message handling for audio pipeline."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        
        # Simulate message handling logic
        async def handle_message(message_type, data):
            if message_type == "tts.started":
                text = data.get("text", "")
                interrupt_manager.clear_interrupt(session_id)
                await mock_websocket.send_json({
                    "type": "tts.acknowledged",
                    "data": {"message": "TTS start acknowledged"}
                })
                
            elif message_type == "user.speaking":
                transcript = data.get("transcript", "")
                interrupted_tts = data.get("interrupted_tts", False)
                interrupted = interrupt_manager.interrupt_session(session_id)
                
                await mock_websocket.send_json({
                    "type": "speech.interrupted",
                    "data": {
                        "success": interrupted,
                        "message": "User speaking, interrupting TTS",
                        "interrupted_tts": interrupted_tts
                    }
                })
                
            elif message_type == "tts.ended":
                await mock_websocket.send_json({
                    "type": "tts.acknowledged",
                    "data": {"message": "TTS end acknowledged"}
                })
        
        # Test TTS start
        await handle_message("tts.started", {"text": "Hello, how can I help you?"})
        mock_websocket.send_json.assert_called_with({
            "type": "tts.acknowledged",
            "data": {"message": "TTS start acknowledged"}
        })
        
        # Test user interruption
        await handle_message("user.speaking", {
            "transcript": "wait let me ask something else",
            "interrupted_tts": True
        })
        
        # Verify interruption response was sent
        last_call = mock_websocket.send_json.call_args_list[-1]
        response = last_call[0][0]
        assert response["type"] == "speech.interrupted"
        assert response["data"]["success"] is True
        assert response["data"]["interrupted_tts"] is True
        
        # Test TTS end
        await handle_message("tts.ended", {"text": "Hello, how can I help you?"})
        
        interrupt_manager.cleanup_session(session_id)

    def test_audio_state_management(self, interrupt_manager):
        """Test audio state management prevents conflicts."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        
        # Initial state: not interrupted
        assert not interrupt_manager.is_interrupted(session_id)
        
        # TTS starts: clear any previous interrupts
        interrupt_manager.clear_interrupt(session_id)
        
        # User interrupts: flag is set
        interrupted = interrupt_manager.interrupt_session(session_id)
        assert interrupted is True
        assert interrupt_manager.is_interrupted(session_id)
        
        # TTS acknowledges interruption: flag is cleared
        interrupt_manager.clear_interrupt(session_id)
        assert not interrupt_manager.is_interrupted(session_id)
        
        interrupt_manager.cleanup_session(session_id)

    def test_multiple_session_isolation(self, interrupt_manager):
        """Test that multiple sessions don't interfere with each other."""
        session1 = "session_1"
        session2 = "session_2"
        
        # Register both sessions
        interrupt_manager.register_session(session1)
        interrupt_manager.register_session(session2)
        
        # Interrupt only session1
        interrupt_manager.interrupt_session(session1)
        
        # Verify isolation
        assert interrupt_manager.is_interrupted(session1) is True
        assert interrupt_manager.is_interrupted(session2) is False
        
        # Clear session1, session2 should be unaffected
        interrupt_manager.clear_interrupt(session1)
        assert interrupt_manager.is_interrupted(session1) is False
        assert interrupt_manager.is_interrupted(session2) is False
        
        # Cleanup
        interrupt_manager.cleanup_session(session1)
        interrupt_manager.cleanup_session(session2)


class TestFrontendAudioLogic:
    """Test the frontend audio logic concepts."""
    
    def test_audio_state_coordination(self):
        """Test the audio state coordination logic."""
        # Simulate frontend state
        class MockFrontend:
            def __init__(self):
                self.isSpeaking = False
                self.isListening = False
                self.voiceInputPaused = False
                
            def start_tts(self):
                self.isSpeaking = True
                if self.isListening:
                    self.pause_voice_input()
                    
            def pause_voice_input(self):
                self.isListening = False
                self.voiceInputPaused = True
                
            def stop_tts(self):
                self.isSpeaking = False
                if self.voiceInputPaused:
                    self.resume_voice_input()
                    
            def resume_voice_input(self):
                self.voiceInputPaused = False
                self.isListening = True
        
        frontend = MockFrontend()
        
        # Test normal flow
        frontend.isListening = True
        assert frontend.isListening is True
        assert frontend.isSpeaking is False
        
        # TTS starts - should pause voice input
        frontend.start_tts()
        assert frontend.isSpeaking is True
        assert frontend.isListening is False
        assert frontend.voiceInputPaused is True
        
        # TTS stops - should resume voice input
        frontend.stop_tts()
        assert frontend.isSpeaking is False
        assert frontend.isListening is True
        assert frontend.voiceInputPaused is False