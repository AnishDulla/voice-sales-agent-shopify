"""Test WebSocket interruption functionality."""

import pytest
from unittest.mock import Mock

from infrastructure.api.routes import SimpleInterruptManager


class TestSimpleInterruptManager:
    """Test the simple interrupt manager."""

    @pytest.fixture
    def interrupt_manager(self):
        """Create a fresh interrupt manager for each test."""
        return SimpleInterruptManager()

    def test_register_session(self, interrupt_manager):
        """Test session registration."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        
        assert session_id in interrupt_manager.active_sessions
        assert interrupt_manager.active_sessions[session_id] is True
        assert interrupt_manager.interrupt_flags[session_id] is False

    def test_interrupt_session_success(self, interrupt_manager):
        """Test successful session interruption."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        
        result = interrupt_manager.interrupt_session(session_id)
        
        assert result is True
        assert interrupt_manager.interrupt_flags[session_id] is True

    def test_interrupt_session_not_registered(self, interrupt_manager):
        """Test interruption fails for unregistered session."""
        result = interrupt_manager.interrupt_session("nonexistent_session")
        
        assert result is False

    def test_is_interrupted(self, interrupt_manager):
        """Test interrupt status checking."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        
        # Initially not interrupted
        assert interrupt_manager.is_interrupted(session_id) is False
        
        # After interruption
        interrupt_manager.interrupt_session(session_id)
        assert interrupt_manager.is_interrupted(session_id) is True

    def test_clear_interrupt(self, interrupt_manager):
        """Test clearing interrupt flag."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        interrupt_manager.interrupt_session(session_id)
        
        # Verify interrupted
        assert interrupt_manager.is_interrupted(session_id) is True
        
        # Clear interrupt
        interrupt_manager.clear_interrupt(session_id)
        assert interrupt_manager.is_interrupted(session_id) is False

    def test_cleanup_session(self, interrupt_manager):
        """Test session cleanup."""
        session_id = "test_session"
        interrupt_manager.register_session(session_id)
        interrupt_manager.interrupt_session(session_id)
        
        # Verify session exists
        assert session_id in interrupt_manager.active_sessions
        assert session_id in interrupt_manager.interrupt_flags
        
        # Cleanup
        interrupt_manager.cleanup_session(session_id)
        
        # Verify cleanup
        assert session_id not in interrupt_manager.active_sessions
        assert session_id not in interrupt_manager.interrupt_flags

    def test_is_interrupted_nonexistent_session(self, interrupt_manager):
        """Test interrupt check for nonexistent session returns False."""
        result = interrupt_manager.is_interrupted("nonexistent_session")
        assert result is False


class TestWebSocketMessageTypes:
    """Test WebSocket message type handling."""

    def test_websocket_has_interrupt_handlers(self):
        """Verify WebSocket handler contains interrupt message types."""
        from infrastructure.api.routes import voice_session
        import inspect
        
        source = inspect.getsource(voice_session)
        
        # Check for required message types
        assert 'interrupt.speech' in source
        assert 'user.speaking' in source
        assert 'speech.interrupted' in source
        
        # Check for interrupt manager usage
        assert 'interrupt_manager' in source
        assert 'register_session' in source
        assert 'interrupt_session' in source
        assert 'cleanup_session' in source