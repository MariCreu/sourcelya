"""Compliance requests, their products, and the audit log

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-13

FASE 3: the supplier-request flow. `status` is a plain VARCHAR (not a
native Postgres enum) — see app/domain/enums.py's module docstring for why
these evolving-state columns are handled this way throughout the app.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("secure_token_hash", sa.String(64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
    )
    op.create_index("ix_compliance_requests_company_id", "compliance_requests", ["company_id"])
    op.create_index("ix_compliance_requests_supplier_id", "compliance_requests", ["supplier_id"])
    op.create_index(
        "ix_compliance_requests_secure_token_hash",
        "compliance_requests",
        ["secure_token_hash"],
        unique=True,
    )

    op.create_table(
        "compliance_request_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["compliance_requests.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.UniqueConstraint("request_id", "product_id", name="uq_request_product"),
    )
    op.create_index(
        "ix_compliance_request_products_request_id", "compliance_request_products", ["request_id"]
    )
    op.create_index(
        "ix_compliance_request_products_product_id", "compliance_request_products", ["product_id"]
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata_json", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index("ix_audit_events_company_id", "audit_events", ["company_id"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("compliance_request_products")
    op.drop_table("compliance_requests")
