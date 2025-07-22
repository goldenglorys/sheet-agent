import uvicorn
from app.core.config import get_settings
import logging
from app.core.logging_config import configure_logging

configure_logging(force=True)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    settings = get_settings()
    
    logger.info(f"Starting SheetAgent API server on {settings.HOST}:{settings.PORT}")
    print(f"Starting SheetAgent API server on {settings.HOST}:{settings.PORT}")
    # Use string reference to module:app so that uvicorn can import it in the worker process
    uvicorn.run(
        "app.app:create_app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        factory=True,
        reload_dirs=["app"],
        log_level="info",
        log_config=None,  # Disable uvicorn's logging config to use ours
    )