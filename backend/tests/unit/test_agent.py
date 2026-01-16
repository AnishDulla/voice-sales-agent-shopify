"""Unit tests for agent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json

from orchestration.agent.graph import VoiceAgent
from shared import AgentState, Intent, ConversationContext, Message


class TestVoiceAgent:
    """Test voice agent."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = AsyncMock()
        return llm
    
    @pytest.fixture
    def agent(self, mock_llm):
        """Create agent with mock LLM."""
        return VoiceAgent(llm=mock_llm)
    
    @pytest.mark.asyncio
    async def test_detect_intent_product_search(self, agent, mock_llm):
        """Test detecting product search intent."""
        state = AgentState(
            session_id="test_session",
            context=ConversationContext(
                session_id="test_session",
                messages=[Message(role="user", content="Show me running shoes")]
            )
        )
        
        mock_response = Mock()
        mock_response.content = "product_search"
        mock_llm.ainvoke.return_value = mock_response
        
        result = await agent.detect_intent(state)
        
        assert result.current_intent == Intent.PRODUCT_SEARCH
        mock_llm.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_route_after_intent(self, agent):
        """Test routing based on intent."""
        state = AgentState(
            session_id="test_session",
            context=ConversationContext(session_id="test_session")
        )
        
        # Product search should route to tool selection
        state.current_intent = Intent.PRODUCT_SEARCH
        assert agent.route_after_intent(state) == "select_tools"
        
        # Unknown intent should route to clarification
        state.current_intent = Intent.UNKNOWN
        state.error_count = 0
        assert agent.route_after_intent(state) == "needs_clarification"
        
        # Too many errors should skip clarification
        state.error_count = 3
        assert agent.route_after_intent(state) == "generate_response"
    
    @pytest.mark.asyncio
    async def test_select_tools(self, agent, mock_llm):
        """Test tool selection."""
        state = AgentState(
            session_id="test_session",
            current_intent=Intent.PRODUCT_SEARCH,
            context=ConversationContext(
                session_id="test_session",
                messages=[Message(role="user", content="Find me Nike shoes")]
            )
        )
        
        # Mock LLM response with tool selection
        mock_response = Mock()
        mock_response.content = json.dumps([{
            "tool": "search_products",
            "parameters": {"query": "Nike shoes", "limit": 5}
        }])
        mock_llm.ainvoke.return_value = mock_response
        
        result = await agent.select_tools(state)
        
        assert result.pending_confirmation is not None
        assert "tool_calls" in result.pending_confirmation
        tool_calls = result.pending_confirmation["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool"] == "search_products"
    
    @pytest.mark.asyncio
    async def test_generate_response(self, agent, mock_llm):
        """Test response generation."""
        state = AgentState(
            session_id="test_session",
            context=ConversationContext(
                session_id="test_session",
                messages=[Message(role="user", content="Show me shoes")]
            ),
            last_tool_results={
                "results": [{
                    "tool": "search_products",
                    "success": True,
                    "data": [
                        {"title": "Nike Air Max", "price": 150},
                        {"title": "Adidas Ultra", "price": 180}
                    ]
                }]
            }
        )
        
        mock_response = Mock()
        mock_response.content = "I found 2 great shoes for you: Nike Air Max for $150 and Adidas Ultra for $180."
        mock_llm.ainvoke.return_value = mock_response
        
        result = await agent.generate_response(state)
        
        # Check response was added to messages
        assert len(result.context.messages) == 2
        assert result.context.messages[-1].role == "assistant"
        assert "Nike Air Max" in result.context.messages[-1].content
    
    @pytest.mark.asyncio
    async def test_process_message_integration(self, agent, mock_llm):
        """Test full message processing."""
        # Set up mock responses for each stage
        mock_responses = [
            Mock(content="product_search"),  # Intent detection
            Mock(content=json.dumps([{  # Tool selection
                "tool": "search_products",
                "parameters": {"query": "shoes"}
            }])),
            Mock(content="I found several shoes for you!")  # Response generation
        ]
        
        mock_llm.ainvoke.side_effect = mock_responses
        
        # Mock tool execution
        with patch('orchestration.tools.registry.registry.execute_tool') as mock_execute:
            mock_execute.return_value = Mock(
                success=True,
                data=[{"title": "Test Shoe", "price": 100}],
                error=None
            )
            
            response = await agent.process_message(
                message="Show me shoes",
                session_id="test_session"
            )
        
        assert response == "I found several shoes for you!"
        assert mock_llm.ainvoke.call_count == 3  # Intent, tools, response