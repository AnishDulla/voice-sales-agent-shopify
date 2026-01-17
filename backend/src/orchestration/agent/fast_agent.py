"""Fast agent implementation with single LLM call and streaming support."""

import json
import re
from typing import Optional, AsyncIterator, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.tools import Tool
from langchain_core.utils.function_calling import convert_to_openai_tool

from shared import (
    ConversationContext,
    Message,
    get_logger
)
from orchestration.tools.registry import registry
from infrastructure.config.settings import get_settings

logger = get_logger(__name__)


class FastVoiceAgent:
    """Optimized voice agent with minimal latency."""
    
    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            api_key=settings.openai_api_key,
            streaming=True  # Enable streaming
        )
        self.tool_registry = registry
        self._setup_tools()
        
    def _setup_tools(self):
        """Setup tools for function calling."""
        self.tools = []
        self.tool_map = {}
        
        for tool_name, tool_instance in self.tool_registry.get_all().items():
            definition = tool_instance.get_definition()
            
            # Create LangChain tool wrapper
            langchain_tool = Tool(
                name=definition.name,
                description=definition.description,
                func=lambda *args, **kwargs: None,  # We'll handle execution manually
            )
            
            self.tools.append(langchain_tool)
            self.tool_map[definition.name] = tool_instance
            
    async def process_message_streaming(
        self,
        message: str,
        session_id: str,
        context: Optional[ConversationContext] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Process message with streaming response and chunked TTS."""
        
        if not context:
            context = ConversationContext(session_id=session_id)
            
        # Add user message to context
        context.messages.append(Message(role="user", content=message))
        
        # Build messages for LLM
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=f"""
User Query: {message}

Available Tools:
- get_product_catalog: Get all products from the catalog
- get_product_details: Get detailed information about a specific product
- check_inventory: Check inventory status for a product

Please:
1. Determine if you need to use any tools to answer the query
2. If yes, call the appropriate tools
3. Generate a natural, conversational response based on the information

Respond in a friendly, helpful tone suitable for voice conversation.
""")
        ]
        
        # Bind tools for function calling
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Stream the response
        full_response = ""
        sentence_buffer = ""
        tool_calls = []
        
        async for chunk in llm_with_tools.astream(messages):
            # Handle tool calls - collect them properly
            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    if hasattr(tc, 'id') and tc.id:  # Only add if it has a valid ID
                        tool_calls.append(tc)
                continue
                
            # Handle text content
            if hasattr(chunk, 'content') and chunk.content:
                text_chunk = chunk.content
                full_response += text_chunk
                sentence_buffer += text_chunk
                
                # Detect complete sentences for TTS chunking
                sentences = self._extract_complete_sentences(sentence_buffer)
                if sentences:
                    for sentence in sentences:
                        yield {
                            "type": "text_chunk",
                            "content": sentence,
                            "trigger_tts": True  # Signal to generate TTS for this chunk
                        }
                    # Keep remainder in buffer
                    sentence_buffer = self._get_sentence_remainder(sentence_buffer)
        
        # Execute any tool calls if needed
        if tool_calls:
            tool_results = await self._execute_tools(tool_calls)
            
            # Generate response based on tool results
            # Format tool calls properly for the AIMessage
            formatted_tool_calls = []
            for tc in tool_calls:
                if hasattr(tc, 'dict'):
                    formatted_tool_calls.append(tc.dict())
                else:
                    formatted_tool_calls.append(tc)
            
            # Create proper message chain
            from langchain_core.messages import ToolMessage
            tool_response_messages = messages + [
                AIMessage(content="", tool_calls=formatted_tool_calls)
            ]
            
            # Add tool results as ToolMessages
            for result in tool_results:
                tool_response_messages.append(
                    ToolMessage(
                        content=result["content"],
                        tool_call_id=result["tool_call_id"]
                    )
                )
            
            # Get final response with tool results
            async for chunk in self.llm.astream(tool_response_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    text_chunk = chunk.content
                    full_response += text_chunk
                    sentence_buffer += text_chunk
                    
                    sentences = self._extract_complete_sentences(sentence_buffer)
                    if sentences:
                        for sentence in sentences:
                            yield {
                                "type": "text_chunk", 
                                "content": sentence,
                                "trigger_tts": True
                            }
                        sentence_buffer = self._get_sentence_remainder(sentence_buffer)
        
        # Send any remaining text
        if sentence_buffer.strip():
            yield {
                "type": "text_chunk",
                "content": sentence_buffer,
                "trigger_tts": True
            }
            
        # Add assistant message to context
        context.messages.append(Message(role="assistant", content=full_response))
        
        # Send completion signal
        yield {
            "type": "completion",
            "full_response": full_response
        }
        
    async def _execute_tools(self, tool_calls: List[Any]) -> List[Any]:
        """Execute tool calls and return results."""
        results = []
        
        for i, tool_call in enumerate(tool_calls):
            # Extract tool info properly
            if hasattr(tool_call, 'name'):
                tool_name = tool_call.name
                tool_args = tool_call.args if hasattr(tool_call, 'args') else {}
                tool_id = tool_call.id if hasattr(tool_call, 'id') else f"tool_{i}"
            else:
                tool_name = tool_call.get('name', '')
                tool_args = tool_call.get('args', {})
                tool_id = tool_call.get('id', f"tool_{i}")
            
            if tool_name in self.tool_map:
                try:
                    result = await self.tool_map[tool_name].execute(**tool_args)
                    
                    # Convert Product objects to dictionaries
                    data = result.data
                    if data and hasattr(data, '__iter__') and not isinstance(data, (str, dict)):
                        # Handle list of objects (like Product objects)
                        data = [item.dict() if hasattr(item, 'dict') else item for item in data]
                    elif data and hasattr(data, 'dict'):
                        # Handle single object
                        data = data.dict()
                    
                    results.append({
                        "role": "tool",
                        "content": json.dumps(data if result.success else {"error": result.error}),
                        "tool_call_id": tool_id  # Always provide a valid string ID
                    })
                except Exception as e:
                    logger.error(f"Tool execution failed for {tool_name}: {e}")
                    results.append({
                        "role": "tool",
                        "content": json.dumps({"error": str(e)}),
                        "tool_call_id": tool_id  # Always provide a valid string ID
                    })
                    
        return results
        
    def _extract_complete_sentences(self, text: str) -> List[str]:
        """Extract complete sentences from text for TTS chunking."""
        # Simple sentence detection - can be improved
        sentences = []
        
        # Look for sentence endings
        pattern = r'[.!?]+[\s]+'
        parts = re.split(pattern, text)
        
        # Check if we have complete sentences
        if len(parts) > 1:
            # All but the last part are complete sentences
            for i in range(len(parts) - 1):
                if parts[i].strip():
                    # Add the punctuation back
                    match = re.search(r'[.!?]+', text[text.find(parts[i]) + len(parts[i]):])
                    if match:
                        sentences.append(parts[i] + match.group())
                        
        return sentences
        
    def _get_sentence_remainder(self, text: str) -> str:
        """Get the remaining incomplete sentence."""
        sentences = self._extract_complete_sentences(text)
        if sentences:
            # Remove complete sentences from text
            for sentence in sentences:
                text = text.replace(sentence, "", 1).strip()
        return text
        
    def _get_system_prompt(self) -> str:
        """Get optimized system prompt."""
        return """You are a helpful voice sales assistant for an e-commerce store. 
You help customers find products, check availability, and answer questions.
Respond conversationally and naturally, as if speaking to someone.
Keep responses concise but friendly.
When listing products, be brief but informative."""

    async def process_message(
        self,
        message: str,
        session_id: str,
        context: Optional[ConversationContext] = None
    ) -> str:
        """Non-streaming version for backwards compatibility."""
        full_response = ""
        
        async for chunk in self.process_message_streaming(message, session_id, context):
            if chunk["type"] == "text_chunk":
                full_response += chunk["content"]
            elif chunk["type"] == "completion":
                return chunk["full_response"]
                
        return full_response