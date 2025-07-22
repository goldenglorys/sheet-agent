"""
FastAPI application factory module.

This module provides a function to create and configure a FastAPI application
with all necessary middleware, exception handlers, and routers.
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator 

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.endpoints import opos, health
from app.core.logging_config import configure_logging

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    # Lifespan Events
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(force=True)
        # Force reconfigure logging to ensure it works with uvicorn
        logger.info("🚀 Starting FastAPI app...")
        # Initialize environment variables if not already done
        app.state.ready = True
        yield
        logger.info("👋 Shutting down FastAPI app...")
        app.state.ready = False

    # Exception Handler
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": str(exc)},
        )
    
    # App Initialization
    app = FastAPI(
        title="WiseBid AI Service",
        description="Backend API for the WiseBid AI service.",
        version="0.1.0",
        lifespan=lifespan,
        # Add security scheme to OpenAPI documentation
        openapi_tags=[
            {
                "name": "Health",
                "description": "Health check endpoints",
            },
            {
                "name": "Documents",
                "description": "Document management endpoints",
            },
            {
                "name": "Protected",
                "description": "Protected endpoints that require authentication",
            },
        ],
    )

    # Add security scheme to OpenAPI documentation
    app.swagger_ui_init_oauth = {"usePkceWithAuthorizationCodeGrant": True}

    app.add_exception_handler(Exception, global_exception_handler)
    
    # Attach routers
    logger.info("=== Attaching Routers ===")
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(opos.router, prefix="/opos", tags=["Open Post Analysis"])    
    return app



