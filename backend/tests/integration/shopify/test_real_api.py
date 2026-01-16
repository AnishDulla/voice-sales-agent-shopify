"""Integration tests for real Shopify API."""

import pytest
import asyncio
from typing import List

from domains.shopify.client import ShopifyClient
from domains.shopify.products import ProductService
from orchestration.tools.product_tools import GetProductCatalogTool
from infrastructure.config.settings import get_settings


@pytest.fixture
async def shopify_client():
    """Create a real Shopify client for testing."""
    settings = get_settings()
    
    if not settings.shopify_store_url or not settings.shopify_access_token:
        pytest.skip("Shopify credentials not configured")
    
    client = ShopifyClient(
        store_url=settings.shopify_store_url,
        access_token=settings.shopify_access_token,
        api_version=settings.shopify_api_version
    )
    
    yield client
    
    await client.close()


@pytest.fixture
async def product_service(shopify_client):
    """Create a product service for testing."""
    return ProductService(shopify_client)


@pytest.fixture
async def catalog_tool(shopify_client):
    """Create a catalog tool for testing."""
    return GetProductCatalogTool(shopify_client=shopify_client)


class TestShopifyAPIConnection:
    """Test basic Shopify API connection."""
    
    async def test_api_connection(self, shopify_client):
        """Test that we can connect to Shopify API."""
        # Try to get products - this will fail if connection is bad
        products = await shopify_client.get_products(limit=1)
        assert isinstance(products, list)
    
    async def test_get_all_products(self, shopify_client):
        """Test getting all products to see what's actually in the store."""
        products = await shopify_client.get_products(limit=250)
        
        print(f"\n=== STORE INVENTORY DEBUG ===")
        print(f"Total products found: {len(products)}")
        
        for i, product in enumerate(products[:10]):  # Show first 10
            print(f"{i+1}. {product.title}")
            print(f"   ID: {product.id}")
            print(f"   Status: {product.status}")
            print(f"   Tags: {product.tags}")
            print(f"   Vendor: {product.vendor}")
            print(f"   Product Type: {product.product_type}")
            if product.variants:
                print(f"   Variants: {len(product.variants)} (${product.variants[0].price})")
            print()
        
        # We should have some products
        assert len(products) > 0, "No products found in store"


class TestProductCatalog:
    """Test product catalog functionality."""
    
    async def test_get_product_catalog(self, catalog_tool):
        """Test getting the full product catalog."""
        print(f"\n=== TESTING CATALOG RETRIEVAL ===")
        
        result = await catalog_tool.execute(limit=10)
        
        print(f"Success: {result.success}")
        print(f"Error: {result.error}")
        print(f"Data count: {len(result.data) if result.data else 0}")
        
        if result.data:
            for i, product in enumerate(result.data[:3]):
                print(f"  {i+1}. {product.title} (${product.price})")
                print(f"      Tags: {product.tags}")
                print(f"      Type: {product.product_type}")
        
        # Should successfully return products
        assert result.success
        assert isinstance(result.data, list)
        assert len(result.data) > 0
        
        # Check metadata
        assert "total_products" in result.metadata
        assert "catalog_type" in result.metadata
        assert result.metadata["catalog_type"] == "full_products"
    
    async def test_catalog_with_different_limits(self, catalog_tool):
        """Test catalog with different limit values."""
        for limit in [5, 25, 50]:
            print(f"\n=== TESTING CATALOG WITH LIMIT {limit} ===")
            
            result = await catalog_tool.execute(limit=limit)
            
            print(f"Success: {result.success}")
            print(f"Data count: {len(result.data) if result.data else 0}")
            print(f"Requested limit: {limit}")
            
            assert result.success
            assert len(result.data) <= limit
            assert result.metadata["limit"] == limit
    
    async def test_catalog_contains_variety(self, catalog_tool):
        """Test that catalog contains different product types."""
        print(f"\n=== TESTING CATALOG VARIETY ===")
        
        result = await catalog_tool.execute(limit=50)
        
        assert result.success
        products = result.data
        
        # Check for variety in product types
        product_types = set()
        vendors = set()
        
        for product in products:
            if product.product_type:
                product_types.add(product.product_type.lower())
            if product.vendor:
                vendors.add(product.vendor.lower())
        
        print(f"Product types found: {len(product_types)}")
        print(f"Vendors found: {len(vendors)}")
        print(f"Sample product types: {list(product_types)[:5]}")
        
        # Should have some variety (at least 1 product type)
        assert len(product_types) > 0


class TestProductService:
    """Test the product service layer."""
    
    async def test_product_service_get_all(self, product_service):
        """Test product service get all products."""
        products = await product_service.get_all_products(limit=15)
        
        print(f"\n=== PRODUCT SERVICE GET ALL ===")
        print(f"Results: {len(products)}")
        
        for product in products[:3]:
            print(f"  - {product.title} (${product.price})")
            print(f"    Type: {product.product_type}")
            print(f"    Tags: {product.tags}")
        
        assert isinstance(products, list)
        assert len(products) > 0
        assert len(products) <= 15


if __name__ == "__main__":
    # Run a quick test
    async def run_quick_test():
        settings = get_settings()
        
        if not settings.shopify_store_url or not settings.shopify_access_token:
            print("❌ Shopify credentials not configured")
            return
        
        client = ShopifyClient(
            store_url=settings.shopify_store_url,
            access_token=settings.shopify_access_token
        )
        
        try:
            print("🔍 Testing Shopify API connection...")
            products = await client.get_products(limit=5)
            print(f"✅ Found {len(products)} products")
            
            for product in products:
                print(f"  - {product.title}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await client.close()
    
    asyncio.run(run_quick_test())