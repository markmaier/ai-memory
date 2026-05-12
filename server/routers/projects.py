import uuid
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import require_auth
from db import get_db
from models import Organization, Project, ProjectMember, User
from schemas import MessageResponse
from server_state import drop_memory_collection, get_memory_for_project

router = APIRouter(prefix="/projects", tags=["projects"])

ALLOWED_MEMBER_ROLES = {"owner", "writer", "reader"}
REQUIRE_AUTH_DEP = cast(Any, require_auth)


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    collection_name: str
    is_personal: bool
    created_at: datetime
    updated_at: datetime
    role: str


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    user_email: str
    role: str
    created_at: datetime


class ProjectDetailsResponse(BaseModel):
    project: ProjectResponse
    members: list[MemberResponse]


class AddMemberRequest(BaseModel):
    email: str
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in ALLOWED_MEMBER_ROLES:
            raise ValueError("Role must be 'owner' or 'reader'.")
        return normalized


class UpdateMemberRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.lower().strip()
        if normalized not in ALLOWED_MEMBER_ROLES:
            raise ValueError("Role must be 'owner' or 'reader'.")
        return normalized


def _get_or_create_organization(db: Session) -> Organization:
    org = db.scalar(select(Organization).order_by(Organization.created_at.asc()))
    if org is None:
        org = Organization(name="My Organization")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def _project_membership_for_user(db: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
    return db.scalar(select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id))


def _to_project_response(project: Project, role: str) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        collection_name=project.collection_name,
        is_personal=project.is_personal,
        created_at=project.created_at,
        updated_at=project.updated_at,
        role=role,
    )


def _list_members(db: Session, project_id: uuid.UUID) -> list[MemberResponse]:
    members = (
        db.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at.asc())
        )
        .all()
    )
    return [
        MemberResponse(
            id=member.id,
            user_id=user.id,
            user_name=user.name,
            user_email=user.email,
            role=member.role,
            created_at=member.created_at,
        )
        for member, user in members
    ]


def _get_project_and_membership_or_403(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Project, ProjectMember]:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    membership = _project_membership_for_user(db, project.id, user_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a project member.")
    return project, membership


def _require_owner(membership: ProjectMember) -> None:
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only project owners can perform this action.")


def _owner_count(db: Session, project_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id, ProjectMember.role == "owner")
    ) or 0


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(body: CreateProjectRequest, user: User = Depends(REQUIRE_AUTH_DEP), db: Session = Depends(get_db)):
    org = _get_or_create_organization(db)
    project = Project(
        org_id=org.id,
        name=body.name,
        description=body.description,
        collection_name=f"memories_{uuid.uuid4()}",
    )
    db.add(project)
    db.flush()

    membership = ProjectMember(project_id=project.id, user_id=user.id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(project)

    return _to_project_response(project, role=membership.role)


@router.get("", response_model=list[ProjectResponse])
def list_projects(user: User = Depends(REQUIRE_AUTH_DEP), db: Session = Depends(get_db)):
    rows = (
        db.execute(
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(Project.created_at.asc())
        )
        .all()
    )
    return [_to_project_response(project, role) for project, role in rows]


@router.get("/{project_id}", response_model=ProjectDetailsResponse)
def get_project(project_id: uuid.UUID, user: User = Depends(REQUIRE_AUTH_DEP), db: Session = Depends(get_db)):
    project, membership = _get_project_and_membership_or_403(db, project_id, user.id)
    return ProjectDetailsResponse(project=_to_project_response(project, membership.role), members=_list_members(db, project.id))


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    user: User = Depends(REQUIRE_AUTH_DEP),
    db: Session = Depends(get_db),
):
    project, membership = _get_project_and_membership_or_403(db, project_id, user.id)
    _require_owner(membership)

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description

    db.commit()
    db.refresh(project)
    return _to_project_response(project, membership.role)


@router.delete("/{project_id}", response_model=MessageResponse)
def delete_project(project_id: uuid.UUID, user: User = Depends(REQUIRE_AUTH_DEP), db: Session = Depends(get_db)):
    project, membership = _get_project_and_membership_or_403(db, project_id, user.id)
    _require_owner(membership)

    if project.is_personal:
        raise HTTPException(status_code=400, detail="Cannot delete a personal project.")

    project_count = db.scalar(select(func.count(Project.id))) or 0
    if project_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last project")

    collection_name = project.collection_name
    db.query(ProjectMember).filter(ProjectMember.project_id == project.id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()

    try:
        memory = get_memory_for_project(collection_name)
        memory.reset()
        drop_memory_collection(collection_name)
    except Exception:
        pass  # DB rows already gone; best-effort vector cleanup

    return MessageResponse(message="Project deleted.")


@router.get("/{project_id}/members", response_model=list[MemberResponse])
def list_members(project_id: uuid.UUID, user: User = Depends(REQUIRE_AUTH_DEP), db: Session = Depends(get_db)):
    project, _ = _get_project_and_membership_or_403(db, project_id, user.id)
    return _list_members(db, project.id)


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=201)
def add_member(
    project_id: uuid.UUID,
    body: AddMemberRequest,
    user: User = Depends(REQUIRE_AUTH_DEP),
    db: Session = Depends(get_db),
):
    project, membership = _get_project_and_membership_or_403(db, project_id, user.id)
    _require_owner(membership)

    if project.is_personal:
        raise HTTPException(status_code=400, detail="Cannot add members to a personal project.")

    member_user = db.scalar(select(User).where(User.email == body.email))
    if member_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    existing_member = _project_membership_for_user(db, project.id, member_user.id)
    if existing_member is not None:
        raise HTTPException(status_code=409, detail="User is already a member.")

    new_member = ProjectMember(project_id=project.id, user_id=member_user.id, role=body.role)
    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return MemberResponse(
        id=new_member.id,
        user_id=member_user.id,
        user_name=member_user.name,
        user_email=member_user.email,
        role=new_member.role,
        created_at=new_member.created_at,
    )


@router.patch("/{project_id}/members/{member_id}", response_model=MemberResponse)
def update_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    body: UpdateMemberRequest,
    user: User = Depends(REQUIRE_AUTH_DEP),
    db: Session = Depends(get_db),
):
    project, membership = _get_project_and_membership_or_403(db, project_id, user.id)
    _require_owner(membership)

    member = db.scalar(select(ProjectMember).where(ProjectMember.id == member_id, ProjectMember.project_id == project.id))
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found.")

    if member.role == "owner" and body.role != "owner" and _owner_count(db, project.id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last owner")

    member.role = body.role
    db.commit()
    db.refresh(member)

    member_user = db.get(User, member.user_id)
    if member_user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return MemberResponse(
        id=member.id,
        user_id=member_user.id,
        user_name=member_user.name,
        user_email=member_user.email,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{project_id}/members/{member_id}", response_model=MessageResponse)
def remove_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    user: User = Depends(REQUIRE_AUTH_DEP),
    db: Session = Depends(get_db),
):
    project, membership = _get_project_and_membership_or_403(db, project_id, user.id)
    _require_owner(membership)

    member = db.scalar(select(ProjectMember).where(ProjectMember.id == member_id, ProjectMember.project_id == project.id))
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found.")

    if member.role == "owner" and _owner_count(db, project.id) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last owner")

    db.delete(member)
    db.commit()
    return MessageResponse(message="Member removed.")
