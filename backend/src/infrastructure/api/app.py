"""FastAPI application setup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from shared import setup_logging, get_logger
from infrastructure.config.settings import get_settings
from orchestration.tools.registry import registry, discover_tools
from domains.shopify.client import ShopifyClient


logger = get_logger(__name__)
settings = get_settings()

# Global instances
shopify_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global shopify_client
    
    # Startup
    logger.info("Starting Voice Sales Agent")
    
    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        json_logs=settings.log_json
    )
    
    # Initialize Shopify client
    shopify_client = ShopifyClient(
        store_url=settings.shopify_store_url,
        access_token=settings.shopify_access_token,
        api_version=settings.shopify_api_version
    )
    
    # Discover and register tools
    try:
        discover_tools("orchestration.tools")
        logger.info(f"Registered {len(registry)} tools")
    except Exception as e:
        logger.error(f"Failed to discover tools: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Voice Sales Agent")
    
    if shopify_client:
        await shopify_client.close()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        debug=settings.debug
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and include routers
    from .routes import router
    app.include_router(router)
    
    return app


# Create app instance
app = create_app()