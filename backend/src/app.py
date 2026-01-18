"""FastAPI application setup."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from config import get_settings
from integrations.shopify.client import ShopifyClient


logger = logging.getLogger(__name__)
settings = get_settings()

shopify_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global shopify_client
    
    logger.info("Starting Backend Service")
    
    shopify_client = ShopifyClient(
        store_url=settings.shopify_store_url,
        access_token=settings.shopify_access_token,
        api_version=settings.shopify_api_version
    )
    
    yield
    
    logger.info("Shutting down Backend Service")
    
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
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    from domains.shopify.routes import router as shopify_router
    from domains.voice.routes import router as voice_router
    
    app.include_router(shopify_router, prefix="/api/shopify", tags=["shopify"])
    app.include_router(voice_router, prefix="/api/voice", tags=["voice"])
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.app_env
        }
    
    return app


app = create_app()