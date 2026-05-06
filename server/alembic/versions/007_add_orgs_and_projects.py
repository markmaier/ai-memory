"""Add organizations, projects, and project membership support

Revision ID: 007
Revises: 006
Create Date: 2026-05-06

"""

from __future__ import annotations

import os
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # pyright: ignore[reportAttributeAccessIssue]

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("collection_name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id"),
    )

    op.add_column("api_keys", sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=True))
    op.add_column("request_logs", sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=True))
    op.drop_index("ix_users_only_one_admin", table_name="users")

    bind = op.get_bind()
    user_count = bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one()
    if user_count:
        org_id = uuid.uuid4()
        project_id = uuid.uuid4()
        collection_name = os.getenv("POSTGRES_COLLECTION_NAME", "memories")
        user_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM users ORDER BY created_at, id"))]

        op.execute(
            sa.text("INSERT INTO organizations (id, name) VALUES (:id, :name)").bindparams(
                id=org_id,
                name="My Organization",
            )
        )
        op.execute(
            sa.text(
                "INSERT INTO projects (id, org_id, name, collection_name, description) "
                "VALUES (:id, :org_id, :name, :collection_name, :description)"
            ).bindparams(
                id=project_id,
                org_id=org_id,
                name="Default",
                collection_name=collection_name,
                description=None,
            )
        )

        for user_id in user_ids:
            op.execute(
                sa.text(
                    "INSERT INTO project_members (id, project_id, user_id, role) "
                    "VALUES (:id, :project_id, :user_id, :role)"
                ).bindparams(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    user_id=user_id,
                    role="owner",
                )
            )

        op.execute(
            sa.text("UPDATE api_keys SET project_id = :project_id WHERE project_id IS NULL").bindparams(
                project_id=project_id,
            )
        )


def downgrade() -> None:
    op.drop_column("request_logs", "project_id")
    op.drop_column("api_keys", "project_id")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("organizations")
    op.create_index(
        "ix_users_only_one_admin",
        "users",
        ["role"],
        unique=True,
        postgresql_where=sa.text("role = 'admin'"),
    )
