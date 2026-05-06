import uuid
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import generate_api_key, require_auth
from db import get_db
from models import APIKey, Project, ProjectMember, User
from schemas import MessageResponse

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateKeyRequest(BaseModel):
    label: str
    project_id: str


class CreateKeyResponse(BaseModel):
    id: str
    key: str
    label: str
    key_prefix: str
    created_at: datetime


class KeyListItem(BaseModel):
    id: str
    label: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    project_id: str | None = None
    project_name: str | None = None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[KeyListItem])
def list_keys(
    project_id: str | None = Query(None),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    stmt = select(APIKey).where(APIKey.created_by == user.id, APIKey.revoked_at.is_(None))
    if project_id is not None:
        stmt = stmt.where(APIKey.project_id == uuid_mod.UUID(project_id))
    stmt = stmt.order_by(APIKey.created_at.desc())

    keys = db.execute(stmt).scalars().all()

    results = []
    for k in keys:
        project_name = None
        if k.project_id is not None:
            project = db.get(Project, k.project_id)
            if project is not None:
                project_name = project.name
        results.append(
            KeyListItem(
                id=str(k.id),
                label=k.label,
                key_prefix=k.key_prefix,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
                project_id=str(k.project_id) if k.project_id else None,
                project_name=project_name,
            )
        )
    return results


@router.post("", response_model=CreateKeyResponse, status_code=201)
def create_key(body: CreateKeyRequest, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    project_uuid = uuid_mod.UUID(body.project_id)
    membership = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_uuid,
            ProjectMember.user_id == user.id,
        )
    ).scalar_one_or_none()

    if membership is None or membership.role != "owner":
        raise HTTPException(status_code=403, detail="You must be an owner of the project to create API keys")

    full_key, prefix, key_hash = generate_api_key()
    api_key = APIKey(
        key_prefix=prefix,
        key_hash=key_hash,
        label=body.label,
        created_by=user.id,
        project_id=project_uuid,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return CreateKeyResponse(
        id=str(api_key.id),
        key=full_key,
        label=api_key.label,
        key_prefix=prefix,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}", response_model=MessageResponse)
def revoke_key(key_id: str, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    try:
        key_uuid = uuid.UUID(key_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="API key not found.")
    api_key = db.get(APIKey, key_uuid)
    if api_key is None or api_key.created_by != user.id:
        raise HTTPException(status_code=404, detail="API key not found.")
    if api_key.revoked_at is not None:
        raise HTTPException(status_code=400, detail="API key is already revoked.")

    api_key.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return MessageResponse(message="API key revoked.")
