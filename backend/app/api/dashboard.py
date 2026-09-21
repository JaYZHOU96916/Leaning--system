from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.dashboard.service import build_library, build_overview
from app.db import get_session

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview")
def dashboard_overview(session: Session = Depends(get_session)) -> dict[str, object]:
    return build_overview(session)


@router.get("/library")
def dashboard_library(session: Session = Depends(get_session)) -> dict[str, object]:
    return build_library(session)
