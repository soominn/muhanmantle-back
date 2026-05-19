from fastapi import APIRouter

from app.schemas.simword import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok"}
