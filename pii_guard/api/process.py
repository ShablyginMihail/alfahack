from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class ProcessRequest(BaseModel):
    payload: str
    payload_id: str = Field(min_length=1, max_length=128)


class ProcessResponse(BaseModel):
    result: str


@router.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest) -> ProcessResponse:
    return ProcessResponse(result=req.payload)
