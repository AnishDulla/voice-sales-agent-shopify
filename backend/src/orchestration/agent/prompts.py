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
- get_product_catalog: Get the full product catalog with all details - YOU do the intelligent filtering
- get_product_details: Get detailed information about a specific product
- check_inventory: Check if products are in stock
"""

INTENT_DETECTION_PROMPT = """Based on the user's message, determine their primary intent.

User message: {message}

IMPORTANT: Pay attention to references like "the first one", "that product", "it", etc. 
These usually indicate the user wants product_details about something from previous conversation.

Possible intents:
- product_search: User wants to find/browse products
- product_details: User wants specific information about a product (including references like "the first one")
- inventory_check: User wants to know if something is in stock
- general_help: User needs general assistance
- unknown: Intent is unclear

Return only the intent name."""

TOOL_SELECTION_PROMPT = """Based on the user's request and intent, select the appropriate tool(s) to use.

IMPORTANT: For product inquiries, use get_product_catalog to get ALL products, then YOU will intelligently filter them.
Do NOT try to pre-filter - let the catalog tool return everything and YOU do the smart matching.

REFERENCE RESOLUTION: If the user says "the first one", "the second one", etc., look in the context for 
last_search_results to find which product they're referring to. Use get_product_details with that product's ID.

User message: {message}
Intent: {intent}
Context: {context}

Available tools:
{tools}

Return a JSON array of tool calls to make, e.g.:
[
  {{
    "tool": "get_product_details",
    "parameters": {{
      "product_id": "specific_product_id_from_context"
    }}
  }}
]

Return an empty array [] if no tools are needed."""

RESPONSE_GENERATION_PROMPT = """Generate a natural, conversational response based on the tool results.

User message: {message}
Tool results: {tool_results}
Context: {context}

IMPORTANT: If you got a full product catalog, YOU must intelligently filter it based on the user's request.
For example, if user asked for "hoodies" and you got all products, find products that are hoodies 
(like "Cloud Hoodie", "Rebel Hoodie", etc.) and present those specifically.

REFERENCE HANDLING: If the user asked about "the first one", "the second one", etc., check the context 
for recent_messages and last_search_results to understand what they're referring to. Acknowledge the 
reference in your response (e.g., "The Cloud Hoodie you mentioned..." or "That first hoodie...").

Guidelines:
- Look through ALL products and find relevant matches using intelligence, not just exact string matches
- Be conversational and helpful  
- Present specific products that match the user's intent
- Include prices and key details
- If you found matches, present them clearly
- If no relevant products exist, explain what you looked through
- When responding to references, acknowledge what they were referring to
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