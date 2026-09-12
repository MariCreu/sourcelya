"""Initial schema: companies, users, suppliers, products, packaging components

Revision ID: 0001
Revises:
Create Date: 2026-09-12

No native Postgres enum types are used here on purpose. `packaging_type` is
a plain VARCHAR validated in the application layer (see
app/domain/enums.py) rather than a DB-level enum, since it's expected to
grow while the product is being validated and a native enum would need an
`ALTER TYPE` migration for every new value. `Product`/`PackagingComponent`
also have no `status` column: compliance status is computed on the fly by
StatusCalculationService, never cached.
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


def upgrade() -> None:
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
        sa.Column("packaging_type", sa.String(50), nullable=False),
        sa.Column("material", sa.String(255), nullable=True),
        sa.Column("weight_grams", sa.Float(), nullable=True),
        sa.Column("recycled_content_percentage", sa.Float(), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("packaging_reference", sa.String(255), nullable=True),
        sa.Column("country_of_manufacture", sa.String(2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    op.create_index("ix_packaging_components_product_id", "packaging_components", ["product_id"])


def downgrade() -> None:
    op.drop_table("packaging_components")
    op.drop_table("products")
    op.drop_table("suppliers")
    op.drop_constraint("fk_users_company_id", "users", type_="foreignkey")
    op.drop_table("companies")
    op.drop_table("users")
