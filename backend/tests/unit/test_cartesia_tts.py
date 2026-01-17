"""Test Cartesia TTS provider selection and configuration."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from infrastructure.livekit.agent import LiveKitVoiceAgent
from infrastructure.config.settings import get_settings


class TestCartesiaTTSSelection:
    """Test TTS provider selection logic."""

    def setup_method(self):
        """Set up test environment."""
        # Clear any cached settings
        if hasattr(get_settings, '_instance'):
            delattr(get_settings, '_instance')

    @patch('livekit.plugins.cartesia.TTS')
    @patch('livekit.plugins.openai.TTS')
    @patch('livekit.plugins.silero.VAD.load')
    @patch.dict(os.environ, {
        "CARTESIA_API_KEY": "test-cartesia-key",
        "CARTESIA_MODEL": "sonic-3",
        "CARTESIA_VOICE_ID": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
        "CARTESIA_SPEED": "1.0",
        "OPENAI_API_KEY": "test-openai-key",
        "SHOPIFY_STORE_URL": "test.myshopify.com",
        "SHOPIFY_ACCESS_TOKEN": "test-token",
        "LIVEKIT_URL": "ws://test",
        "LIVEKIT_API_KEY": "test",
        "LIVEKIT_API_SECRET": "test"
    })
    def test_uses_cartesia_when_api_key_present(self, mock_vad, mock_openai_tts, mock_cartesia_tts):
        """Verify Cartesia TTS is used when API key is present."""
        # Setup mocks
        mock_cartesia_instance = Mock()
        mock_cartesia_tts.return_value = mock_cartesia_instance
        mock_vad.return_value = Mock()
        
        # Create agent
        agent = LiveKitVoiceAgent()
        
        # Verify Cartesia TTS was called
        mock_cartesia_tts.assert_called_once_with(
            model="sonic-3",
            voice="f786b574-daa5-4673-aa0c-cbe3e8534c02",
            speed=1.0
        )
        
        # Verify OpenAI TTS was NOT called
        mock_openai_tts.assert_not_called()
        
        # Verify agent has Cartesia TTS instance
        assert agent.tts == mock_cartesia_instance
        print("✓ Test passed: Cartesia TTS is used when API key is present")

    @patch('livekit.plugins.cartesia.TTS')
    @patch('livekit.plugins.openai.TTS')
    @patch('livekit.plugins.silero.VAD.load')
    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-openai-key",
        "SHOPIFY_STORE_URL": "test.myshopify.com",
        "SHOPIFY_ACCESS_TOKEN": "test-token",
        "LIVEKIT_URL": "ws://test",
        "LIVEKIT_API_KEY": "test",
        "LIVEKIT_API_SECRET": "test",
        "TTS_VOICE": "alloy"
    }, clear=True)
    def test_fallback_to_openai_when_no_cartesia_key(self, mock_vad, mock_openai_tts, mock_cartesia_tts):
        """Verify OpenAI TTS is used when no Cartesia API key."""
        # Setup mocks
        mock_openai_instance = Mock()
        mock_openai_tts.return_value = mock_openai_instance
        mock_vad.return_value = Mock()
        
        # Create agent
        agent = LiveKitVoiceAgent()
        
        # Verify OpenAI TTS was called
        mock_openai_tts.assert_called_once_with(voice="alloy")
        
        # Verify Cartesia TTS was NOT called
        mock_cartesia_tts.assert_not_called()
        
        # Verify agent has OpenAI TTS instance
        assert agent.tts == mock_openai_instance
        print("✓ Test passed: OpenAI TTS is used when no Cartesia API key")

    @patch('livekit.plugins.cartesia.TTS')
    @patch('livekit.plugins.openai.TTS')
    @patch('livekit.plugins.silero.VAD.load')
    @patch.dict(os.environ, {
        "CARTESIA_API_KEY": "",  # Empty API key
        "OPENAI_API_KEY": "test-openai-key",
        "SHOPIFY_STORE_URL": "test.myshopify.com",
        "SHOPIFY_ACCESS_TOKEN": "test-token",
        "LIVEKIT_URL": "ws://test",
        "LIVEKIT_API_KEY": "test",
        "LIVEKIT_API_SECRET": "test",
        "TTS_VOICE": "alloy"
    })
    def test_fallback_to_openai_when_empty_cartesia_key(self, mock_vad, mock_openai_tts, mock_cartesia_tts):
        """Verify OpenAI TTS is used when Cartesia API key is empty."""
        # Setup mocks
        mock_openai_instance = Mock()
        mock_openai_tts.return_value = mock_openai_instance
        mock_vad.return_value = Mock()
        
        # Create agent
        agent = LiveKitVoiceAgent()
        
        # Verify OpenAI TTS was called (empty string is falsy)
        mock_openai_tts.assert_called_once_with(voice="alloy")
        
        # Verify Cartesia TTS was NOT called
        mock_cartesia_tts.assert_not_called()
        
        # Verify agent has OpenAI TTS instance
        assert agent.tts == mock_openai_instance
        print("✓ Test passed: OpenAI TTS is used when Cartesia API key is empty")

    @patch('livekit.plugins.silero.VAD.load')
    def test_cartesia_initialization_parameters_from_real_settings(self, mock_vad):
        """Verify correct parameters are passed to Cartesia TTS using real settings."""
        mock_vad.return_value = Mock()
        
        with patch.dict(os.environ, {
            "CARTESIA_API_KEY": "sk_car_real_key",
            "CARTESIA_MODEL": "sonic-3",
            "CARTESIA_VOICE_ID": "test-voice-123",
            "CARTESIA_SPEED": "1.5",
            "OPENAI_API_KEY": "test-openai-key",
            "SHOPIFY_STORE_URL": "test.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test-token",
            "LIVEKIT_URL": "ws://test",
            "LIVEKIT_API_KEY": "test",
            "LIVEKIT_API_SECRET": "test"
        }):
            with patch('livekit.plugins.cartesia.TTS') as mock_cartesia:
                mock_cartesia_instance = Mock()
                mock_cartesia.return_value = mock_cartesia_instance
                
                # Create agent
                agent = LiveKitVoiceAgent()
                
                # Verify Cartesia TTS was called with correct parameters
                mock_cartesia.assert_called_once_with(
                    model="sonic-3",
                    voice="test-voice-123",
                    speed=1.5  # Should be converted to float
                )
                
                # Verify agent has the right instance
                assert agent.tts == mock_cartesia_instance
                print("✓ Test passed: Cartesia TTS receives correct parameters from settings")

    def test_agent_tts_instance_type_verification(self):
        """Integration test to verify the actual TTS instance type."""
        with patch.dict(os.environ, {
            "CARTESIA_API_KEY": "sk_car_test_key",
            "CARTESIA_MODEL": "sonic-3",
            "CARTESIA_VOICE_ID": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
            "CARTESIA_SPEED": "1.0",
            "OPENAI_API_KEY": "test-openai-key",
            "SHOPIFY_STORE_URL": "test.myshopify.com",
            "SHOPIFY_ACCESS_TOKEN": "test-token",
            "LIVEKIT_URL": "ws://test",
            "LIVEKIT_API_KEY": "test",
            "LIVEKIT_API_SECRET": "test"
        }):
            # Mock VAD to avoid ONNX issues
            with patch('livekit.plugins.silero.VAD.load') as mock_vad:
                mock_vad.return_value = Mock()
                
                # Create agent - this will use real TTS imports
                agent = LiveKitVoiceAgent()
                
                # Check the TTS instance type
                tts_class_name = agent.tts.__class__.__name__
                tts_module = agent.tts.__class__.__module__
                
                print(f"TTS Class: {tts_class_name}")
                print(f"TTS Module: {tts_module}")
                
                # Verify it's a Cartesia TTS instance
                assert "cartesia" in tts_module.lower() or "cartesia" in tts_class_name.lower(), \
                    f"Expected Cartesia TTS, but got {tts_module}.{tts_class_name}"
                
                print("✓ Test passed: Agent uses actual Cartesia TTS instance")

    def test_agent_configuration_logging(self):
        """Test that we can inspect the agent's TTS configuration."""
        with patch.dict(os.environ, {
            "CARTESIA_API_KEY": "sk_car_test_key",
            "CARTESIA_MODEL": "sonic-3", 
            "CARTESIA_VOICE_ID": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
            "CARTESIA_SPEED": "1.0",
            "OPENAI_API_KEY": "test-openai-key",
            "SHOPIFY_STORE_URL": "test.myshopify.com", 
            "SHOPIFY_ACCESS_TOKEN": "test-token",
            "LIVEKIT_URL": "ws://test",
            "LIVEKIT_API_KEY": "test",
            "LIVEKIT_API_SECRET": "test"
        }):
            with patch('livekit.plugins.silero.VAD.load') as mock_vad:
                mock_vad.return_value = Mock()
                
                # Create agent
                agent = LiveKitVoiceAgent()
                
                # Inspect the TTS object
                print(f"TTS object: {agent.tts}")
                print(f"TTS type: {type(agent.tts)}")
                print(f"TTS attributes: {dir(agent.tts)}")
                
                # Try to access TTS configuration if available
                if hasattr(agent.tts, '_model'):
                    print(f"TTS model: {agent.tts._model}")
                if hasattr(agent.tts, '_voice'):
                    print(f"TTS voice: {agent.tts._voice}")
                if hasattr(agent.tts, '_speed'):
                    print(f"TTS speed: {agent.tts._speed}")
                
                print("✓ Test passed: Agent TTS configuration inspected")


def run_manual_test():
    """Manual test runner for debugging."""
    test_instance = TestCartesiaTTSSelection()
    
    print("Running Cartesia TTS Tests...")
    print("=" * 50)
    
    try:
        test_instance.setup_method()
        test_instance.test_uses_cartesia_when_api_key_present()
    except Exception as e:
        print(f"❌ test_uses_cartesia_when_api_key_present failed: {e}")
    
    try:
        test_instance.setup_method()
        test_instance.test_fallback_to_openai_when_no_cartesia_key()
    except Exception as e:
        print(f"❌ test_fallback_to_openai_when_no_cartesia_key failed: {e}")
    
    try:
        test_instance.setup_method()
        test_instance.test_fallback_to_openai_when_empty_cartesia_key()
    except Exception as e:
        print(f"❌ test_fallback_to_openai_when_empty_cartesia_key failed: {e}")
    
    try:
        test_instance.setup_method()
        test_instance.test_cartesia_initialization_parameters_from_real_settings()
    except Exception as e:
        print(f"❌ test_cartesia_initialization_parameters_from_real_settings failed: {e}")
    
    try:
        test_instance.setup_method()
        test_instance.test_agent_tts_instance_type_verification()
    except Exception as e:
        print(f"❌ test_agent_tts_instance_type_verification failed: {e}")
    
    try:
        test_instance.setup_method() 
        test_instance.test_agent_configuration_logging()
    except Exception as e:
        print(f"❌ test_agent_configuration_logging failed: {e}")
    
    print("=" * 50)
    print("Tests completed!")


if __name__ == "__main__":
    run_manual_test()