from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import AnalysisListItem, AnalysisReport, OperativeNote
from app.safety.phi_detector import contains_phi_like_identifier
from app.services.analysis_service import PHI_REJECTION_MESSAGE, AnalysisService

router = APIRouter(prefix="/api", tags=["analyses"])
service = AnalysisService()


@router.post("/notes", response_model=AnalysisReport, status_code=status.HTTP_201_CREATED)
def submit_note(payload: OperativeNote, db: Session = Depends(get_db)) -> AnalysisReport:
    if contains_phi_like_identifier(f"{payload.title}\n{payload.note_text}"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PHI_REJECTION_MESSAGE)
    try:
        return service.create_analysis(db, payload)
    except ValueError as exc:
        if str(exc) == PHI_REJECTION_MESSAGE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=PHI_REJECTION_MESSAGE) from exc
        raise


@router.get("/analyses", response_model=list[AnalysisListItem])
def list_analyses(db: Session = Depends(get_db)) -> list[AnalysisListItem]:
    return service.list_recent_analyses(db)


@router.get("/analyses/{analysis_id}", response_model=AnalysisReport)
def get_analysis(analysis_id: UUID, db: Session = Depends(get_db)) -> AnalysisReport:
    try:
        return service.get_analysis(db, analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: UUID, db: Session = Depends(get_db)) -> dict:
    try:
        return service.export_analysis(db, analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
