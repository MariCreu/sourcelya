"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

compliance_status = postgresql.ENUM(
    "green", "orange", "red", name="compliance_status"
)
request_status = postgresql.ENUM(
    "draft", "sent", "opened", "in_progress", "submitted", "review_required", "completed",
    name="request_status",
)
packaging_type = postgresql.ENUM(
    "box", "bag", "label", "filler", "outer_envelope", "other", name="packaging_type"
)
document_type = postgresql.ENUM(
    "spec_sheet", "test_report", "certificate", "invoice", "photo", "other",
    name="document_type",
)
extraction_status = postgresql.ENUM(
    "pending", "processing", "completed", "failed", name="extraction_status"
)
extracted_field_entity_type = postgresql.ENUM(
    "packaging_component", "product", name="extracted_field_entity_type"
)
audit_event_type = postgresql.ENUM(
    "request_created", "request_sent", "request_opened", "document_uploaded",
    "request_submitted", "field_accepted", "field_edited", "reminder_sent",
    name="audit_event_type",
)


def upgrade() -> None:
    bind = op.get_bind()
    compliance_status.create(bind, checkfirst=True)
    request_status.create(bind, checkfirst=True)
    packaging_type.create(bind, checkfirst=True)
    document_type.create(bind, checkfirst=True)
    extraction_status.create(bind, checkfirst=True)
    extracted_field_entity_type.create(bind, checkfirst=True)
    audit_event_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
    )

    op.create_foreign_key(
        "fk_users_company_id", "users", "companies", ["company_id"], ["id"]
    )

    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
    )
    op.create_index("ix_suppliers_company_id", "suppliers", ["company_id"])

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", compliance_status, nullable=False, server_default="orange"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
    )
    op.create_index("ix_products_company_id", "products", ["company_id"])
    op.create_index("ix_products_supplier_id", "products", ["supplier_id"])

    op.create_table(
        "packaging_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("packaging_type", packaging_type, nullable=False),
        sa.Column("material", sa.String(255), nullable=True),
        sa.Column("weight_grams", sa.Float(), nullable=True),
        sa.Column("recycled_content_percentage", sa.Float(), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("packaging_reference", sa.String(255), nullable=True),
        sa.Column("country_of_manufacture", sa.String(2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", compliance_status, nullable=False, server_default="orange"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_packaging_components_product_id", "packaging_components", ["product_id"])

    op.create_table(
        "compliance_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", request_status, nullable=False, server_default="draft"),
        sa.Column("secure_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index(
        "ix_compliance_request_products_request_id", "compliance_request_products", ["request_id"]
    )
    op.create_index(
        "ix_compliance_request_products_product_id", "compliance_request_products", ["product_id"]
    )

    op.create_table(
        "supplier_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("document_type", document_type, nullable=False, server_default="other"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "extraction_status", extraction_status, nullable=False, server_default="pending"
        ),
        sa.ForeignKeyConstraint(["request_id"], ["compliance_requests.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_supplier_documents_request_id", "supplier_documents", ["request_id"])
    op.create_index("ix_supplier_documents_supplier_id", "supplier_documents", ["supplier_id"])
    op.create_index("ix_supplier_documents_product_id", "supplier_documents", ["product_id"])

    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", extracted_field_entity_type, nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("extracted_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["supplier_document_id"], ["supplier_documents.id"]),
    )
    op.create_index(
        "ix_extracted_fields_supplier_document_id", "extracted_fields", ["supplier_document_id"]
    )
    op.create_index("ix_extracted_fields_entity_id", "extracted_fields", ["entity_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", audit_event_type, nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
    )
    op.create_index("ix_audit_events_company_id", "audit_events", ["company_id"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("extracted_fields")
    op.drop_table("supplier_documents")
    op.drop_table("compliance_request_products")
    op.drop_table("compliance_requests")
    op.drop_table("packaging_components")
    op.drop_table("products")
    op.drop_table("suppliers")
    op.drop_constraint("fk_users_company_id", "users", type_="foreignkey")
    op.drop_table("companies")
    op.drop_table("users")

    bind = op.get_bind()
    audit_event_type.drop(bind, checkfirst=True)
    extracted_field_entity_type.drop(bind, checkfirst=True)
    extraction_status.drop(bind, checkfirst=True)
    document_type.drop(bind, checkfirst=True)
    packaging_type.drop(bind, checkfirst=True)
    request_status.drop(bind, checkfirst=True)
    compliance_status.drop(bind, checkfirst=True)
