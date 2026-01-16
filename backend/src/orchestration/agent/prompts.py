"""Agent prompts and templates."""

SYSTEM_PROMPT = """You are a helpful voice sales assistant for an online store. 
You help customers find products, answer questions about inventory, and provide information about items in the catalog.

Your capabilities include:
- Searching for products by name, category, or other attributes
- Providing detailed product information
- Checking inventory availability
- Answering questions about products

Be conversational, helpful, and guide customers to find what they're looking for.
If you're not sure about something, ask clarifying questions.

Available tools:
- search_products: Find products matching search criteria
- get_product_details: Get detailed information about a specific product
- check_inventory: Check if products are in stock
"""

INTENT_DETECTION_PROMPT = """Based on the user's message, determine their primary intent.

User message: {message}

Possible intents:
- product_search: User wants to find/browse products
- product_details: User wants specific information about a product
- inventory_check: User wants to know if something is in stock
- general_help: User needs general assistance
- unknown: Intent is unclear

Return only the intent name."""

TOOL_SELECTION_PROMPT = """Based on the user's request and intent, select the appropriate tool(s) to use.

User message: {message}
Intent: {intent}
Context: {context}

Available tools:
{tools}

Return a JSON array of tool calls to make, e.g.:
[
  {{
    "tool": "search_products",
    "parameters": {{
      "query": "running shoes",
      "limit": 5
    }}
  }}
]

Return an empty array [] if no tools are needed."""

RESPONSE_GENERATION_PROMPT = """Generate a natural, conversational response based on the tool results.

User message: {message}
Tool results: {tool_results}
Context: {context}

Guidelines:
- Be conversational and helpful
- Summarize key information clearly
- Suggest next steps when appropriate
- If no results were found, offer alternatives
- Keep responses concise for voice interaction

Response:"""

CLARIFICATION_PROMPT = """The user's request needs clarification. Ask a helpful question to better understand what they're looking for.

User message: {message}
Context: {context}

Generate a clarifying question:"""

ERROR_RESPONSE_PROMPT = """An error occurred while processing the request. Generate a helpful response.

User message: {message}
Error: {error}

Generate a helpful response that:
- Acknowledges the issue
- Suggests alternatives if possible
- Maintains a positive tone

Response:"""