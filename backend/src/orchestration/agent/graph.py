"""LangGraph agent implementation."""

from typing import Dict, List, Any, Optional, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import json

from shared import (
    AgentState,
    Intent,
    Message,
    ConversationContext,
    get_logger
)
from orchestration.tools.registry import registry, ToolSelector
from orchestration.tools.base import ToolContext
from infrastructure.config.settings import get_settings
from .prompts import (
    SYSTEM_PROMPT,
    INTENT_DETECTION_PROMPT,
    TOOL_SELECTION_PROMPT,
    RESPONSE_GENERATION_PROMPT,
    CLARIFICATION_PROMPT,
    ERROR_RESPONSE_PROMPT
)


logger = get_logger(__name__)


class VoiceAgent:
    """Voice sales agent using LangGraph."""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        tool_registry: Optional[Any] = None
    ):
        settings = get_settings()
        self.llm = llm or ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            api_key=settings.openai_api_key
        )
        self.tool_registry = tool_registry or registry
        self.tool_selector = ToolSelector(self.tool_registry)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the agent graph."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("detect_intent", self.detect_intent)
        workflow.add_node("select_tools", self.select_tools)
        workflow.add_node("execute_tools", self.execute_tools)
        workflow.add_node("generate_response", self.generate_response)
        workflow.add_node("handle_error", self.handle_error)
        workflow.add_node("clarify", self.clarify)
        
        # Add edges
        workflow.set_entry_point("detect_intent")
        
        workflow.add_conditional_edges(
            "detect_intent",
            self.route_after_intent,
            {
                "needs_clarification": "clarify",
                "select_tools": "select_tools",
                "generate_response": "generate_response"
            }
        )
        
        workflow.add_edge("select_tools", "execute_tools")
        workflow.add_edge("execute_tools", "generate_response")
        workflow.add_edge("generate_response", END)
        workflow.add_edge("clarify", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    async def detect_intent(self, state: AgentState) -> AgentState:
        """Detect user intent from the message."""
        try:
            last_message = state.context.messages[-1].content if state.context.messages else ""
            
            prompt = INTENT_DETECTION_PROMPT.format(message=last_message)
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            intent_str = response.content.strip().lower()
            
            # Map to Intent enum
            intent_map = {
                "product_search": Intent.PRODUCT_SEARCH,
                "product_details": Intent.PRODUCT_DETAILS,
                "inventory_check": Intent.PRODUCT_DETAILS,  # Use same intent
                "general_help": Intent.GENERAL_HELP,
            }
            
            state.current_intent = intent_map.get(intent_str, Intent.UNKNOWN)
            
            logger.info(
                "intent_detected",
                session_id=state.session_id,
                intent=state.current_intent,
                message=last_message[:100]
            )
            
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            state.current_intent = Intent.UNKNOWN
            state.error_count += 1
        
        return state
    
    def route_after_intent(self, state: AgentState) -> Literal["needs_clarification", "select_tools", "generate_response"]:
        """Route based on detected intent."""
        if state.current_intent == Intent.UNKNOWN and state.error_count < 3:
            return "needs_clarification"
        elif state.current_intent in [Intent.PRODUCT_SEARCH, Intent.PRODUCT_DETAILS]:
            return "select_tools"
        else:
            return "generate_response"
    
    async def select_tools(self, state: AgentState) -> AgentState:
        """Select appropriate tools based on intent and context."""
        try:
            last_message = state.context.messages[-1].content if state.context.messages else ""
            
            # Get available tools
            tools_info = []
            for tool in self.tool_registry.get_all().values():
                definition = tool.get_definition()
                tools_info.append({
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": [p.dict() for p in definition.parameters]
                })
            
            prompt = TOOL_SELECTION_PROMPT.format(
                message=last_message,
                intent=state.current_intent,
                context=self._get_context_summary(state),
                tools=json.dumps(tools_info, indent=2)
            )
            
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Parse tool calls
            try:
                tool_calls = json.loads(response.content)
                state.pending_confirmation = {"tool_calls": tool_calls}
            except json.JSONDecodeError:
                logger.warning("Failed to parse tool selection")
                state.pending_confirmation = {"tool_calls": []}
            
        except Exception as e:
            logger.error(f"Tool selection failed: {e}")
            state.error_count += 1
        
        return state
    
    async def execute_tools(self, state: AgentState) -> AgentState:
        """Execute selected tools."""
        try:
            tool_calls = state.pending_confirmation.get("tool_calls", []) if state.pending_confirmation else []
            results = []
            
            for call in tool_calls:
                tool_name = call.get("tool")
                parameters = call.get("parameters", {})
                
                if not tool_name:
                    continue
                
                logger.info(
                    "executing_tool",
                    tool_name=tool_name,
                    parameters=parameters,
                    session_id=state.session_id
                )
                
                try:
                    result = await self.tool_registry.execute_tool(
                        tool_name,
                        **parameters
                    )
                    
                    results.append({
                        "tool": tool_name,
                        "success": result.success,
                        "data": result.data,
                        "error": result.error
                    })
                    
                except Exception as e:
                    logger.error(f"Tool execution failed for {tool_name}: {e}")
                    results.append({
                        "tool": tool_name,
                        "success": False,
                        "error": str(e)
                    })
            
            state.last_tool_results = {"results": results}
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            state.error_count += 1
        
        return state
    
    async def generate_response(self, state: AgentState) -> AgentState:
        """Generate final response based on tool results."""
        try:
            last_message = state.context.messages[-1].content if state.context.messages else ""
            tool_results = state.last_tool_results or {}
            
            prompt = RESPONSE_GENERATION_PROMPT.format(
                message=last_message,
                tool_results=json.dumps(tool_results, indent=2),
                context=self._get_context_summary(state)
            )
            
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            # Add response to conversation
            state.context.messages.append(Message(
                role="assistant",
                content=response.content,
                metadata={
                    "intent": state.current_intent,
                    "tools_used": [
                        r["tool"] for r in tool_results.get("results", [])
                    ] if tool_results else []
                }
            ))
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state.error_count += 1
            # Fallback response
            state.context.messages.append(Message(
                role="assistant",
                content="I apologize, but I'm having trouble processing your request. Could you please try again?"
            ))
        
        return state
    
    async def clarify(self, state: AgentState) -> AgentState:
        """Ask for clarification when intent is unclear."""
        try:
            last_message = state.context.messages[-1].content if state.context.messages else ""
            
            prompt = CLARIFICATION_PROMPT.format(
                message=last_message,
                context=self._get_context_summary(state)
            )
            
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            state.context.messages.append(Message(
                role="assistant",
                content=response.content,
                metadata={"type": "clarification"}
            ))
            
        except Exception as e:
            logger.error(f"Clarification failed: {e}")
            state.context.messages.append(Message(
                role="assistant",
                content="I didn't quite understand that. Could you tell me more about what you're looking for?"
            ))
        
        return state
    
    async def handle_error(self, state: AgentState) -> AgentState:
        """Handle errors gracefully."""
        try:
            last_message = state.context.messages[-1].content if state.context.messages else ""
            error_msg = "An error occurred while processing your request"
            
            prompt = ERROR_RESPONSE_PROMPT.format(
                message=last_message,
                error=error_msg
            )
            
            response = await self.llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            state.context.messages.append(Message(
                role="assistant",
                content=response.content,
                metadata={"type": "error"}
            ))
            
        except Exception as e:
            logger.error(f"Error handling failed: {e}")
            state.context.messages.append(Message(
                role="assistant",
                content="I apologize for the inconvenience. Let me try to help you in a different way."
            ))
        
        return state
    
    def _get_context_summary(self, state: AgentState) -> str:
        """Get a summary of the conversation context."""
        summary = {
            "message_count": len(state.context.messages),
            "cart_items": len(state.context.cart_items),
            "viewed_products": state.context.viewed_products[-5:],  # Last 5
            "user_preferences": state.context.user_preferences
        }
        return json.dumps(summary)
    
    async def process_message(
        self,
        message: str,
        session_id: str,
        context: Optional[ConversationContext] = None
    ) -> str:
        """Process a user message and return response."""
        # Initialize context if not provided
        if not context:
            context = ConversationContext(session_id=session_id)
        
        # Add user message
        context.messages.append(Message(role="user", content=message))
        
        # Create initial state
        state = AgentState(
            session_id=session_id,
            context=context
        )
        
        # Run the graph
        try:
            final_state = await self.graph.ainvoke(state)
            
            # Get the last assistant message
            assistant_messages = [
                msg for msg in final_state["context"].messages
                if msg.role == "assistant"
            ]
            
            if assistant_messages:
                return assistant_messages[-1].content
            else:
                return "I'm here to help you find products. What are you looking for?"
                
        except Exception as e:
            logger.error(f"Agent processing failed: {e}")
            return "I apologize, but I encountered an error. Please try again."