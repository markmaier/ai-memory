import uuid
from datetime import datetime

from auth import require_admin
from db import get_db
from fastapi import APIRouter, Depends, Query
from models import RequestLog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/requests", tags=["requests"])


class RequestLogItem(BaseModel):
    id: uuid.UUID
    method: str
    path: str
    status_code: int
    latency_ms: float
    auth_type: str
    project_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


API_KEY_AUTH_TYPES = ("api_key", "admin_api_key")


@router.get("", response_model=list[RequestLogItem])
def list_requests(
    _auth=Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    project_id: str | None = Query(default=None),
):
    stmt = select(RequestLog).where(RequestLog.auth_type.in_(API_KEY_AUTH_TYPES))

    if project_id is not None:
        try:
            pid = uuid.UUID(project_id)
        except (TypeError, ValueError):
            pid = None
        if pid is not None:
            stmt = stmt.where(RequestLog.project_id == pid)

    stmt = stmt.order_by(RequestLog.created_at.desc()).limit(limit)
    logs = db.execute(stmt).scalars().all()
    return logs
