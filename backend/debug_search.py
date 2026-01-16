#!/usr/bin/env python3
"""Debug the actual search functionality."""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from domains.shopify.client import ShopifyClient
from domains.shopify.products import ProductService
from orchestration.tools.product_tools import SearchProductsTool
from infrastructure.config.settings import get_settings
from shared.utils import normalize_product_query
from shared import SearchFilters


async def debug_search_issue():
    """Debug exactly what's happening in the search."""
    print("🔍 Debugging Search Issue...")
    
    settings = get_settings()
    client = ShopifyClient(
        store_url=settings.shopify_store_url,
        access_token=settings.shopify_access_token,
        api_version=settings.shopify_api_version
    )
    
    try:
        # Step 1: Raw Shopify API call
        print("\n1. RAW SHOPIFY API CALL:")
        all_products = await client.get_products(limit=250)
        print(f"   Total products from API: {len(all_products)}")
        
        hoodie_products = [p for p in all_products if "hoodie" in p.title.lower()]
        print(f"   Products with 'hoodie' in title: {len(hoodie_products)}")
        for p in hoodie_products:
            print(f"     - {p.title}")
        
        # Step 2: Client search method
        print("\n2. CLIENT SEARCH METHOD:")
        search_results = await client.search_products("hoodie", limit=10)
        print(f"   Client search results: {len(search_results)}")
        for p in search_results:
            print(f"     - {p.title}")
            
        search_results_plural = await client.search_products("hoodies", limit=10)
        print(f"   Client search 'hoodies': {len(search_results_plural)}")
        for p in search_results_plural:
            print(f"     - {p.title}")
        
        # Step 3: Product Service
        print("\n3. PRODUCT SERVICE:")
        product_service = ProductService(client)
        
        filters = SearchFilters(limit=10, sort_by="relevance")
        service_results = await product_service.search_products("hoodie", filters)
        print(f"   Service search results: {len(service_results)}")
        for p in service_results:
            print(f"     - {p.title} (${p.price})")
            
        service_results_plural = await product_service.search_products("hoodies", filters)
        print(f"   Service search 'hoodies': {len(service_results_plural)}")
        for p in service_results_plural:
            print(f"     - {p.title} (${p.price})")
        
        # Step 4: Search Tool
        print("\n4. SEARCH TOOL:")
        search_tool = SearchProductsTool(shopify_client=client)
        
        tool_result = await search_tool.execute(query="hoodie", limit=10)
        print(f"   Tool search 'hoodie': Success={tool_result.success}, Count={len(tool_result.data) if tool_result.data else 0}")
        if tool_result.error:
            print(f"   Error: {tool_result.error}")
        if tool_result.data:
            for p in tool_result.data:
                print(f"     - {p.title} (${p.price})")
        
        tool_result_plural = await search_tool.execute(query="hoodies", limit=10)
        print(f"   Tool search 'hoodies': Success={tool_result_plural.success}, Count={len(tool_result_plural.data) if tool_result_plural.data else 0}")
        if tool_result_plural.error:
            print(f"   Error: {tool_result_plural.error}")
        if tool_result_plural.data:
            for p in tool_result_plural.data:
                print(f"     - {p.title} (${p.price})")
        
        # Step 5: Query normalization
        print("\n5. QUERY NORMALIZATION:")
        normalized_hoodie = normalize_product_query("hoodie")
        normalized_hoodies = normalize_product_query("hoodies")
        print(f"   'hoodie' -> '{normalized_hoodie}'")
        print(f"   'hoodies' -> '{normalized_hoodies}'")
        
        normalized_tool_result = await search_tool.execute(query=normalized_hoodies, limit=10)
        print(f"   Tool search normalized: Success={normalized_tool_result.success}, Count={len(normalized_tool_result.data) if normalized_tool_result.data else 0}")
        if normalized_tool_result.data:
            for p in normalized_tool_result.data:
                print(f"     - {p.title} (${p.price})")
                
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(debug_search_issue())