"""Ultra-optimized voice agent with minimal latency."""

import json
import re
import time
from typing import Optional, AsyncIterator, Dict, Any, List
import openai
from openai import AsyncOpenAI

from shared import (
    ConversationContext,
    Message,
    get_logger
)
from orchestration.tools.registry import registry
from infrastructure.config.settings import get_settings

logger = get_logger(__name__)


class OptimizedVoiceAgent:
    """Single-shot optimized agent with streaming and chunked TTS."""
    
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.tool_registry = registry
        self.tools = self._prepare_tools()
        
    def _prepare_tools(self) -> List[Dict[str, Any]]:
        """Prepare tools in OpenAI function format."""
        tools = []
        
        # Add product catalog tool
        tools.append({
            "type": "function",
            "function": {
                "name": "get_product_catalog",
                "description": "Get all products from the catalog",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of products to return",
                            "default": 50
                        }
                    }
                }
            }
        })
        
        # Add product details tool
        tools.append({
            "type": "function",
            "function": {
                "name": "get_product_details",
                "description": "Get detailed information about a specific product",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "The product ID"
                        }
                    },
                    "required": ["product_id"]
                }
            }
        })
        
        return tools
    
    async def process_message_streaming(
        self,
        message: str,
        session_id: str,
        context: Optional[ConversationContext] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """Process message with streaming response and sentence-level TTS."""
        
        start_time = time.time()
        
        if not context:
            context = ConversationContext(session_id=session_id)
        
        # Add user message
        context.messages.append(Message(role="user", content=message))
        
        try:
            # Build messages with concise system prompt
            messages = [
                {
                    "role": "system",
                    "content": """You are a helpful voice assistant for an e-commerce store.
CRITICAL: Keep responses VERY SHORT - maximum 2-3 sentences for voice.
When listing products, mention only name and price initially.
End with "Would you like more details?" if applicable.
Example: "I found 2 hoodies. The Cloud Hoodie for $89 and Mountain Hoodie for $95. Would you like more details?"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
            
            logger.info(f"Starting OpenAI call at {time.time() - start_time:.2f}s")
            
            # Make single OpenAI call with tools
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                stream=True
            )
            
            # Process streaming response
            full_response = ""
            sentence_buffer = ""
            tool_calls = []
            current_tool_call = None
            
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if not delta:
                    continue
                
                # Handle tool calls
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        if tool_call_delta.index == 0 and tool_call_delta.id:
                            # New tool call
                            if current_tool_call:
                                tool_calls.append(current_tool_call)
                            current_tool_call = {
                                "id": tool_call_delta.id,
                                "name": tool_call_delta.function.name if tool_call_delta.function else "",
                                "arguments": tool_call_delta.function.arguments if tool_call_delta.function else ""
                            }
                        elif current_tool_call:
                            # Accumulate arguments
                            if tool_call_delta.function and tool_call_delta.function.arguments:
                                current_tool_call["arguments"] += tool_call_delta.function.arguments
                            if tool_call_delta.function and tool_call_delta.function.name:
                                current_tool_call["name"] = tool_call_delta.function.name
                
                # Handle text content
                if delta.content:
                    text_chunk = delta.content
                    full_response += text_chunk
                    sentence_buffer += text_chunk
                    
                    # Check for sentence completion
                    sentences = self._extract_sentences(sentence_buffer)
                    if sentences:
                        for sentence in sentences[:-1]:  # All but last (might be incomplete)
                            if sentence.strip():
                                logger.info(f"Sentence ready at {time.time() - start_time:.2f}s: {sentence[:50]}...")
                                yield {
                                    "type": "text_chunk",
                                    "content": sentence,
                                    "trigger_tts": True
                                }
                        # Keep the last part as buffer
                        sentence_buffer = sentences[-1] if sentences else ""
            
            # Add final tool call if exists
            if current_tool_call:
                tool_calls.append(current_tool_call)
            
            # Execute tools if needed
            if tool_calls:
                logger.info(f"Executing {len(tool_calls)} tools at {time.time() - start_time:.2f}s")
                tool_results = await self._execute_tools(tool_calls)
                
                # Add tool results to messages and get final response
                messages.append({
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"]
                            }
                        } for tc in tool_calls
                    ]
                })
                
                for tool_result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": tool_result["content"]
                    })
                
                # Get final response with tool results
                logger.info(f"Getting final response at {time.time() - start_time:.2f}s")
                final_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True
                )
                
                async for chunk in final_response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        text_chunk = delta.content
                        full_response += text_chunk
                        sentence_buffer += text_chunk
                        
                        sentences = self._extract_sentences(sentence_buffer)
                        if sentences:
                            for sentence in sentences[:-1]:
                                if sentence.strip():
                                    logger.info(f"Final sentence at {time.time() - start_time:.2f}s: {sentence[:50]}...")
                                    yield {
                                        "type": "text_chunk",
                                        "content": sentence,
                                        "trigger_tts": True
                                    }
                            sentence_buffer = sentences[-1] if sentences else ""
            
            # Send any remaining text
            if sentence_buffer.strip():
                logger.info(f"Final buffer at {time.time() - start_time:.2f}s")
                yield {
                    "type": "text_chunk",
                    "content": sentence_buffer,
                    "trigger_tts": True
                }
            
            # Add to context
            context.messages.append(Message(role="assistant", content=full_response))
            
            # Send completion
            logger.info(f"Complete at {time.time() - start_time:.2f}s")
            yield {
                "type": "completion",
                "full_response": full_response
            }
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            error_msg = "I apologize, but I encountered an error. Please try again."
            yield {
                "type": "text_chunk",
                "content": error_msg,
                "trigger_tts": True
            }
            yield {
                "type": "completion",
                "full_response": error_msg
            }
    
    async def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_id = tool_call["id"]
            
            try:
                # Parse arguments
                args = json.loads(tool_call["arguments"]) if tool_call["arguments"] else {}
                
                # Execute tool
                if tool_name in ["get_product_catalog", "get_product_details", "check_inventory"]:
                    tool = self.tool_registry.get(tool_name)
                    if tool:
                        result = await tool.execute(**args)
                        
                        # Convert to JSON-serializable format using model_dump for proper datetime handling
                        data = result.data
                        if data and hasattr(data, '__iter__') and not isinstance(data, (str, dict)):
                            # Use model_dump with mode='json' for proper datetime serialization
                            data = [
                                item.model_dump(mode='json') if hasattr(item, 'model_dump') 
                                else item.dict() if hasattr(item, 'dict') 
                                else item 
                                for item in data
                            ]
                        elif data and hasattr(data, 'model_dump'):
                            # Use model_dump for Pydantic v2 models
                            data = data.model_dump(mode='json')
                        elif data and hasattr(data, 'dict'):
                            # Fallback for older Pydantic models
                            data = data.dict()
                        
                        
                        results.append({
                            "tool_call_id": tool_id,
                            "content": json.dumps({"success": True, "data": data})
                        })
                    else:
                        results.append({
                            "tool_call_id": tool_id,
                            "content": json.dumps({"success": False, "error": f"Tool {tool_name} not found"})
                        })
                else:
                    results.append({
                        "tool_call_id": tool_id,
                        "content": json.dumps({"success": False, "error": f"Unknown tool: {tool_name}"})
                    })
                    
            except Exception as e:
                logger.error(f"Tool execution error for {tool_name}: {e}")
                results.append({
                    "tool_call_id": tool_id,
                    "content": json.dumps({"success": False, "error": str(e)})
                })
        
        return results
    
    def _extract_sentences(self, text: str) -> List[str]:
        """Extract sentences for chunking."""
        # Split on sentence endings
        sentences = re.split(r'([.!?]+\s+)', text)
        
        # Reconstruct sentences with their punctuation
        result = []
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                result.append(sentences[i] + sentences[i + 1])
            else:
                result.append(sentences[i])
        
        return [s for s in result if s.strip()]
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        context: Optional[ConversationContext] = None
    ) -> str:
        """Non-streaming fallback."""
        full_response = ""
        
        async for chunk in self.process_message_streaming(message, session_id, context):
            if chunk["type"] == "text_chunk":
                full_response += chunk["content"]
            elif chunk["type"] == "completion":
                return chunk["full_response"]
        
        return full_response