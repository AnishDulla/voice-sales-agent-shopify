"""Test multi-turn conversation with product references."""

import pytest
from unittest.mock import AsyncMock, Mock

from shared.types import ConversationContext, Message, AgentState, Intent
from orchestration.agent.graph import VoiceAgent


class TestMultiTurnConversation:
    """Test multi-turn conversation capabilities."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM for testing."""
        llm = AsyncMock()
        return llm

    @pytest.fixture
    def mock_tool_registry(self):
        """Mock tool registry."""
        registry = Mock()
        search_tool = Mock()
        search_tool.execute = AsyncMock(return_value=Mock(
            success=True,
            data=[
                Mock(dict=lambda: {
                    "id": "1",
                    "title": "Cloud Hoodie",
                    "price": 50.0,
                    "description": "Light blue wash with tighter fit"
                }),
                Mock(dict=lambda: {
                    "id": "2", 
                    "title": "Rebel Hoodie",
                    "price": 85.0,
                    "description": "Cool graphic design streetwear"
                })
            ]
        ))
        registry.get_all.return_value = {"search_products": search_tool}
        registry.get.return_value = search_tool
        registry.execute_tool = search_tool.execute
        return registry

    @pytest.fixture
    def agent(self, mock_llm, mock_tool_registry):
        """Create agent with mocked dependencies."""
        return VoiceAgent(llm=mock_llm, tool_registry=mock_tool_registry)

    @pytest.mark.asyncio
    async def test_multiturn_product_reference(self, agent, mock_llm):
        """Test that agent can resolve 'the first one' reference."""
        # Setup mock responses
        mock_llm.ainvoke.side_effect = [
            # Intent detection for first message
            Mock(content="product_search"),
            # Tool selection for first message  
            Mock(content='[{"tool": "search_products", "parameters": {"query": "hoodies"}}]'),
            # Response generation for first message
            Mock(content="I found these hoodies: 1. Cloud Hoodie ($50) 2. Rebel Hoodie ($85)"),
            # Intent detection for second message
            Mock(content="product_details"),
            # Tool selection for second message (should identify Cloud Hoodie)
            Mock(content='[{"tool": "get_product_details", "parameters": {"product_id": "1"}}]'),
            # Response generation for second message
            Mock(content="The Cloud Hoodie is a light blue wash with tighter fit...")
        ]

        # Create conversation context
        context = ConversationContext(session_id="test_session")
        
        # First turn: "what hoodies do you have?"
        response1 = await agent.process_message(
            message="what hoodies do you have?",
            session_id="test_session", 
            context=context
        )
        
        assert "Cloud Hoodie" in response1
        assert "Rebel Hoodie" in response1
        
        # Second turn: "tell me more about the first one"
        response2 = await agent.process_message(
            message="tell me more about the first one",
            session_id="test_session",
            context=context
        )
        
        # Verify the agent understood "the first one" refers to Cloud Hoodie
        assert "Cloud Hoodie" in response2 or "light blue" in response2
        
        # Verify conversation history was used in the LLM call
        # The LLM should have been called with context that includes previous messages
        calls = mock_llm.ainvoke.call_args_list
        
        # Check that later calls include conversation history
        later_call = calls[-2]  # Tool selection call for second message
        call_messages = later_call[0][0]
        
        # Should contain previous conversation in some form
        conversation_content = " ".join([msg.content for msg in call_messages])
        assert "Cloud Hoodie" in conversation_content or "hoodies" in conversation_content

    @pytest.mark.asyncio
    async def test_context_summary_includes_messages(self, agent):
        """Test that context summary includes recent messages."""
        # Create context with messages
        context = ConversationContext(session_id="test_session")
        context.messages = [
            Message(role="user", content="what hoodies do you have?"),
            Message(role="assistant", content="I found these hoodies: 1. Cloud Hoodie ($50)"),
            Message(role="user", content="tell me more about the first one")
        ]
        
        state = AgentState(session_id="test_session", context=context)
        
        # Get context summary
        summary = agent._get_context_summary(state)
        
        # Summary should include recent messages for reference resolution
        assert "Cloud Hoodie" in summary or "hoodies" in summary or "first one" in summary

    @pytest.mark.asyncio  
    async def test_tool_results_stored_for_reference(self, agent, mock_llm, mock_tool_registry):
        """Test that tool results are stored and accessible for follow-up."""
        mock_llm.ainvoke.side_effect = [
            Mock(content="product_search"),
            Mock(content='[{"tool": "search_products", "parameters": {"query": "hoodies"}}]'),
            Mock(content="I found these hoodies")
        ]
        
        context = ConversationContext(session_id="test_session")
        
        await agent.process_message(
            message="what hoodies do you have?",
            session_id="test_session",
            context=context  
        )
        
        # Create state to check stored results
        state = AgentState(session_id="test_session", context=context)
        
        # Agent should have stored the search results for later reference
        # This will need to be implemented in the fix
        assert hasattr(agent, '_last_search_results') or hasattr(state, 'last_tool_results')