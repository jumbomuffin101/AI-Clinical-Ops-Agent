from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import AnalysisReport, OperativeNote
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/api", tags=["analyses"])
service = AnalysisService()


@router.post("/notes", response_model=AnalysisReport, status_code=status.HTTP_201_CREATED)
def submit_note(payload: OperativeNote, db: Session = Depends(get_db)) -> AnalysisReport:
    return service.create_analysis(db, payload)


@router.get("/analyses/{analysis_id}", response_model=AnalysisReport)
def get_analysis(analysis_id: UUID, db: Session = Depends(get_db)) -> AnalysisReport:
    try:
        return service.get_analysis(db, analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
