import time

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from pii_guard.observability.logging import get_logger

router = APIRouter()

logger = get_logger("pii_guard.process")


class ProcessRequest(BaseModel):
    payload: str
    payload_id: str = Field(min_length=1, max_length=128)


class ProcessResponse(BaseModel):
    result: str


@router.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest, request: Request) -> ProcessResponse:
    service = request.app.state.process_service
    start = time.perf_counter()
    outcome = await service.handle(req.payload_id, req.payload)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "process",
        payload_id=req.payload_id,
        direction=outcome.direction,
        payload_len=len(req.payload),
        pii=outcome.type_counts,
        duration_ms=round(duration_ms, 3),
    )
    return ProcessResponse(result=outcome.result)
