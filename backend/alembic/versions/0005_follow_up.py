"""Missing-information follow-up loop: FollowUpRound + ComplianceRequest columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-13

FASE 6: closes the "ask -> respond -> extract -> review -> ask again for
only what's missing -> complete" loop. `RequestStatus.REVIEW_REQUIRED` is
dropped (never used, would now collide with the computed
`InformationStatus.REVIEW_REQUIRED`) — no data migration needed since no
row ever held that value.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "compliance_requests",
        sa.Column("automatic_follow_up", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "compliance_requests",
        sa.Column("fields_available_after_first_submission", sa.Integer(), nullable=True),
    )

    op.create_table(
        "follow_up_rounds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("requested_fields", postgresql.JSONB(), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("available_count_before", sa.Integer(), nullable=False),
        sa.Column("missing_count_before", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["compliance_requests.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_follow_up_rounds_company_id", "follow_up_rounds", ["company_id"])
    op.create_index("ix_follow_up_rounds_request_id", "follow_up_rounds", ["request_id"])


def downgrade() -> None:
    op.drop_table("follow_up_rounds")
    op.drop_column("compliance_requests", "fields_available_after_first_submission")
    op.drop_column("compliance_requests", "automatic_follow_up")
