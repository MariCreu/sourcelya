"""Supplier documents

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-13

FASE 4: a supplier can attach files to a request through the public
portal. `document_type`/`extraction_status` are plain VARCHAR (not native
Postgres enums) — see app/domain/enums.py's module docstring for why.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False, server_default="other"),
        sa.Column("extraction_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["compliance_requests.id"]),
        sa.UniqueConstraint("storage_path", name="uq_supplier_documents_storage_path"),
    )
    op.create_index("ix_supplier_documents_company_id", "supplier_documents", ["company_id"])
    op.create_index("ix_supplier_documents_supplier_id", "supplier_documents", ["supplier_id"])
    op.create_index("ix_supplier_documents_product_id", "supplier_documents", ["product_id"])
    op.create_index("ix_supplier_documents_request_id", "supplier_documents", ["request_id"])


def downgrade() -> None:
    op.drop_table("supplier_documents")
