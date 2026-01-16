"""Main application entry point."""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from shared import setup_logging, get_logger
from infrastructure.config.settings import get_settings
from infrastructure.api.app import app

logger = get_logger(__name__)
settings = get_settings()


def main():
    """Main entry point."""
    # Setup logging
    setup_logging(
        log_level=settings.log_level,
        json_logs=settings.log_json
    )
    
    logger.info(
        "Starting Voice Sales Agent",
        environment=settings.app_env,
        version=settings.app_version,
        config=settings.mask_sensitive()
    )
    
    # Run the application
    uvicorn.run(
        "src.infrastructure.api.app:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower()
    )


def run_livekit_agent():
    """Run the LiveKit agent separately."""
    from infrastructure.livekit.agent import run_agent
    
    logger.info("Starting LiveKit voice agent")
    run_agent()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice Sales Agent")
    parser.add_argument(
        "--mode",
        choices=["api", "livekit", "both"],
        default="api",
        help="Run mode: api server, livekit agent, or both"
    )
    
    args = parser.parse_args()
    
    if args.mode == "api":
        main()
    elif args.mode == "livekit":
        run_livekit_agent()
    elif args.mode == "both":
        # Run both in separate processes
        import multiprocessing
        
        api_process = multiprocessing.Process(target=main)
        livekit_process = multiprocessing.Process(target=run_livekit_agent)
        
        api_process.start()
        livekit_process.start()
        
        try:
            api_process.join()
            livekit_process.join()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            api_process.terminate()
            livekit_process.terminate()