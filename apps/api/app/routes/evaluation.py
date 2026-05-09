from fastapi import APIRouter

from app.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])
service = EvaluationService()


@router.get("/summary")
def evaluation_summary() -> dict:
    return service.run()
