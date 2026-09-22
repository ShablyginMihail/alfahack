from fastapi import APIRouter
from fastapi.responses import Response

from pii_guard.observability.metrics import metrics_response

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    return Response(
        content=metrics_response(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
