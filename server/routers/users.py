import uuid
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import require_admin, require_auth
from db import get_db
from models import Project, ProjectMember, User
from schemas import MessageResponse
from server_state import drop_memory_collection, get_memory_for_project

router = APIRouter(prefix="/users", tags=["users"])

REQUIRE_ADMIN_DEP = cast(Any, require_admin)
REQUIRE_AUTH_DEP = cast(Any, require_auth)


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[UserResponse])
def list_users(admin: User = Depends(REQUIRE_ADMIN_DEP), db: Session = Depends(get_db)):
    """List all registered users. Admin only."""
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return users


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(REQUIRE_ADMIN_DEP),
    db: Session = Depends(get_db),
):
    """Delete a user, their personal project memories, and all project memberships. Admin only."""

    # Cannot delete yourself
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")

    # Block if the user is the sole owner of any non-personal project
    sole_owned = (
        db.execute(
            select(Project.name)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                ProjectMember.user_id == user_id,
                ProjectMember.role == "owner",
                Project.is_personal.is_(False),
            )
        )
        .scalars()
        .all()
    )
    # For each candidate, check if there is another owner
    blocking_projects = []
    for project_name in sole_owned:
        project = db.scalar(select(Project).where(Project.name == project_name))
        if project is None:
            continue
        other_owner_count = db.scalar(
            select(func.count(ProjectMember.id)).where(
                ProjectMember.project_id == project.id,
                ProjectMember.role == "owner",
                ProjectMember.user_id != user_id,
            )
        ) or 0
        if other_owner_count == 0:
            blocking_projects.append(project_name)

    if blocking_projects:
        names = ", ".join(f'"{n}"' for n in blocking_projects)
        raise HTTPException(
            status_code=400,
            detail=f"User is the sole owner of project(s) {names}. Transfer ownership before deleting.",
        )

    # Collect and drop personal project vector collections before removing DB rows
    personal_projects = (
        db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user_id, Project.is_personal.is_(True))
        )
        .scalars()
        .all()
    )

    # Remove all project memberships
    db.query(ProjectMember).filter(ProjectMember.user_id == user_id).delete(
        synchronize_session=False
    )

    # Delete personal projects (no other members, safe to remove)
    for project in personal_projects:
        db.delete(project)

    # Delete the user
    db.delete(target)
    db.commit()

    # Best-effort: drop vector collections for personal projects
    for project in personal_projects:
        try:
            memory = get_memory_for_project(project.collection_name)
            memory.reset()
            drop_memory_collection(project.collection_name)
        except Exception:
            pass

    return MessageResponse(message="User deleted.")
