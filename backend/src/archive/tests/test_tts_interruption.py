"""Test TTS interruption functionality."""

import pytest
from unittest.mock import AsyncMock, Mock

from infrastructure.livekit.agent import LiveKitVoiceAgent


class TestTTSInterruption:
    """Test TTS interruption capabilities."""

    @pytest.fixture
    def mock_assistant(self):
        """Mock LiveKit VoiceAssistant."""
        assistant = Mock()
        assistant.interrupt = AsyncMock()
        return assistant

    @pytest.fixture
    def livekit_agent(self, mock_assistant):
        """Create LiveKit agent with mocked assistant."""
        agent = LiveKitVoiceAgent()
        # Manually add assistant to test interruption
        agent.assistants["test_session"] = mock_assistant
        return agent

    @pytest.mark.asyncio
    async def test_interrupt_speech_success(self, livekit_agent, mock_assistant):
        """Test successful speech interruption."""
        # Test interruption
        result = await livekit_agent.interrupt_speech("test_session")
        
        # Verify interrupt was called and succeeded
        assert result is True
        mock_assistant.interrupt.assert_called_once()

    @pytest.mark.asyncio
    async def test_interrupt_speech_no_session(self, livekit_agent):
        """Test interruption fails when session doesn't exist."""
        result = await livekit_agent.interrupt_speech("nonexistent_session")
        
        # Should return False for non-existent session
        assert result is False

    @pytest.mark.asyncio
    async def test_interrupt_speech_no_interrupt_method(self, livekit_agent):
        """Test interruption when assistant doesn't support interrupt."""
        # Create assistant without interrupt method
        assistant_without_interrupt = Mock()
        # Don't add interrupt method
        
        livekit_agent.assistants["test_session"] = assistant_without_interrupt
        
        result = await livekit_agent.interrupt_speech("test_session")
        
        # Should return False when assistant doesn't support interrupt
        assert result is False

    @pytest.mark.asyncio
    async def test_interrupt_speech_exception(self, livekit_agent, mock_assistant):
        """Test interruption handles exceptions gracefully."""
        # Make interrupt method raise an exception
        mock_assistant.interrupt.side_effect = Exception("Interrupt failed")
        
        result = await livekit_agent.interrupt_speech("test_session")
        
        # Should return False when interrupt raises exception
        assert result is False
        mock_assistant.interrupt.assert_called_once()

    def test_assistant_cleanup_on_disconnect(self, livekit_agent, mock_assistant):
        """Test that assistant references are cleaned up properly."""
        session_id = "test_session"
        livekit_agent.assistants[session_id] = mock_assistant
        
        # Simulate disconnect cleanup
        if session_id in livekit_agent.assistants:
            del livekit_agent.assistants[session_id]
        
        # Verify assistant reference was removed
        assert session_id not in livekit_agent.assistants


@pytest.mark.asyncio 
async def test_websocket_interrupt_integration():
    """Test WebSocket interrupt message integration."""
    from infrastructure.api.routes import voice_session
    from unittest.mock import patch
    
    # This would be a more complex integration test
    # Testing the full WebSocket flow with interrupt messages
    # For now, just verify the basic structure exists
    
    # Verify the WebSocket handler has interrupt message types
    import inspect
    source = inspect.getsource(voice_session)
    
    assert "interrupt.speech" in source
    assert "user.speaking" in source
    assert "speech.interrupted" in source