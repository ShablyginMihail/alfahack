from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    store = request.app.state.store
    try:
        ok = await store.ping()
    except Exception:
        ok = False
    if not ok:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    backend = store.backend
    return JSONResponse(
        content={
            "status": "ready",
            "store": backend,
            "degraded": backend == "redis-degraded",
        }
    )
