"""Main application entry point."""

import uvicorn
import logging
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


def main():
    """Main entry point."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version} "
        f"in {settings.app_env} environment"
    )
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()