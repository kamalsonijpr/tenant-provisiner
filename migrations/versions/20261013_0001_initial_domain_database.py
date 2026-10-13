"""initial domain database

Revision ID: 20261013_0001
Revises:
Create Date: 2026-10-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=28), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "provisioning",
                "active",
                "updating",
                "destroying",
                "destroyed",
                "failed",
                name="tenant_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(name) > 0", name=op.f("ck_tenants_tenant_name_not_empty")),
        sa.CheckConstraint(
            "slug ~ '^[a-z][-a-z0-9]{1,26}[a-z0-9]$'",
            name=op.f("ck_tenants_tenant_slug_format"),
        ),
        sa.CheckConstraint(
            "length(slug) BETWEEN 3 AND 28",
            name=op.f("ck_tenants_tenant_slug_length"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_tenants_tenant_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index("ix_tenants_created_at_id", "tenants", ["created_at", "id"])
    op.create_index("ix_tenants_status_created_at", "tenants", ["status", "created_at"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("exchange", sa.String(length=255), nullable=False),
        sa.Column("routing_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(
        "ix_outbox_events_created_at_id",
        "outbox_events",
        ["created_at", "id"],
    )
    op.create_index(
        "ix_outbox_events_published_at_created_at",
        "outbox_events",
        ["published_at", "created_at"],
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "deploy",
                "update",
                "destroy",
                name="task_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "accepted",
                "in_progress",
                "done",
                "failed",
                name="task_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_tasks_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index("ix_tasks_created_at_id", "tasks", ["created_at", "id"])
    op.create_index("ix_tasks_status_created_at", "tasks", ["status", "created_at"])
    op.create_index("ix_tasks_tenant_id_created_at", "tasks", ["tenant_id", "created_at"])
    op.create_index("ix_tasks_type_created_at", "tasks", ["type", "created_at"])

    op.create_table(
        "processed_worker_updates",
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_processed_worker_updates_task_id_tasks"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("idempotency_key", name=op.f("pk_processed_worker_updates")),
    )
    op.create_index(
        "ix_processed_worker_updates_task_id_received_at",
        "processed_worker_updates",
        ["task_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_processed_worker_updates_task_id_received_at",
        table_name="processed_worker_updates",
    )
    op.drop_table("processed_worker_updates")
    op.drop_index("ix_tasks_type_created_at", table_name="tasks")
    op.drop_index("ix_tasks_tenant_id_created_at", table_name="tasks")
    op.drop_index("ix_tasks_status_created_at", table_name="tasks")
    op.drop_index("ix_tasks_created_at_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_outbox_events_published_at_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_created_at_id", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index("ix_tenants_status_created_at", table_name="tenants")
    op.drop_index("ix_tenants_created_at_id", table_name="tenants")
    op.drop_table("tenants")
