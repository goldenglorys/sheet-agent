from fastapi import APIRouter, HTTPException, status, Request

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """Health check to confirm service is running."""
    return {"status": "ok"}


@router.get("/ready", tags=["Health"])
async def readiness_check(request: Request):
    """Readiness check to confirm app is ready."""
    if not hasattr(request.app.state, "ready") or not request.app.state.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application is not ready yet",
        )
    return {"status": "ready"}
