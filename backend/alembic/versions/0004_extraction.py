"""Document extraction: ExtractedField + SupplierDocument bookkeeping columns

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-13

FASE 5: structured, evidenced extraction of packaging fields from supplier
documents. `field_name`/`confidence`/`review_status` are plain VARCHAR, not
native Postgres enums — see app/domain/enums.py's module docstring for why.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "supplier_documents", sa.Column("processing_error", sa.Text(), nullable=True)
    )
    op.add_column(
        "supplier_documents",
        sa.Column("extraction_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "supplier_documents", sa.Column("extraction_model", sa.String(100), nullable=True)
    )
    op.add_column(
        "supplier_documents", sa.Column("extraction_duration_ms", sa.Integer(), nullable=True)
    )
    op.add_column(
        "supplier_documents", sa.Column("extraction_input_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "supplier_documents", sa.Column("extraction_output_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "supplier_documents", sa.Column("extraction_cost_usd", sa.Float(), nullable=True)
    )

    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("packaging_component_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("extracted_value", sa.String(500), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("quote_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["supplier_documents.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["compliance_requests.id"]),
        sa.ForeignKeyConstraint(["packaging_component_id"], ["packaging_components.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_extracted_fields_company_id", "extracted_fields", ["company_id"])
    op.create_index("ix_extracted_fields_document_id", "extracted_fields", ["document_id"])
    op.create_index("ix_extracted_fields_request_id", "extracted_fields", ["request_id"])
    op.create_index(
        "ix_extracted_fields_packaging_component_id",
        "extracted_fields",
        ["packaging_component_id"],
    )


def downgrade() -> None:
    op.drop_table("extracted_fields")
    op.drop_column("supplier_documents", "extraction_cost_usd")
    op.drop_column("supplier_documents", "extraction_output_tokens")
    op.drop_column("supplier_documents", "extraction_input_tokens")
    op.drop_column("supplier_documents", "extraction_duration_ms")
    op.drop_column("supplier_documents", "extraction_model")
    op.drop_column("supplier_documents", "extraction_attempts")
    op.drop_column("supplier_documents", "processing_error")
