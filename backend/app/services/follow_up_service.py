"""Closes the "ask -> respond -> extract -> review -> ask again for only
what's missing -> complete" loop (FASE 6).

Two entry points:

- `create_round()` — explicitly creates and sends one follow-up round,
  asking the supplier for exactly the fields `MissingInformationService`
  currently reports as missing. Used directly by the company's "Request
  missing information" button (manual — always allowed, never capped,
  since a human is already deciding each time), and by `reevaluate()`
  below for automatic follow-up (opt-in, capped).
- `reevaluate()` — the single shared hook called right after anything that
  could change completeness (`PublicRequestService.submit`,
  `ExtractedFieldService.accept`/`reject`): recomputes
  `MissingInformationService`, flips the request to `COMPLETED` (+ sends a
  one-time thank-you email) the moment everything is available, and — only
  if `ComplianceRequest.automatic_follow_up` is set — attempts an
  automatic follow-up round through the exact same guarded path a human
  would use.

Token handling: every round mints a brand-new token via the same
`generate_secure_token`/`hash_token` primitives `ComplianceRequestService`
already uses for send()/resend() — not a new decision. `secure_token_hash`
is a one-way hash with no raw token ever stored, so re-emailing *any*
working link, for *any* reason, always requires minting a fresh one; the
previous link stops working the moment a new one is issued, exactly like
`resend()` already does. See the FASE 6 report's "Token: challenge y
decisión" for why an initial preference for "keep the same token across
rounds" turned out to be technically impossible, not just undesirable.

No new scheduler: automatic follow-up fires from the same request-response
cycle that already changed the data (submit/accept/reject), never from a
periodic job — consistent with this codebase's "no in-process scheduler,
no Celery/Redis" stance (see the root README's "Why not an in-process
scheduler for jobs").
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import generate_secure_token, hash_token
from app.domain.enums import AuditEventType, InformationStatus, RequestStatus
from app.integrations.email.templates import (
    ComplianceRequestEmailContext,
    MissingFieldRef,
    MissingInformationFollowUpEmailContext,
    RequestCompleteEmailContext,
)
from app.models.company import Company
from app.models.compliance_request import ComplianceRequest
from app.models.follow_up_round import FollowUpRound
from app.repositories.follow_up_round_repository import FollowUpRoundRepository
from app.repositories.supplier_document_repository import SupplierDocumentRepository
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.missing_information_service import (
    MissingInformationService,
    RequestInformationSummary,
)


class NothingMissingError(Exception):
    """The request is already InformationStatus.COMPLETE — nothing to ask for."""


class ExtractionStillProcessingError(Exception):
    """At least one of this request's documents hasn't finished processing
    yet — following up now could ask for something that's about to arrive."""


class ReviewRequiredBeforeFollowUpError(Exception):
    """There's a pending proposal (possibly conflicting, possibly
    unresolved-component) that a human needs to accept/reject/resolve
    before Sourcelya can honestly say what's still missing."""


class DuplicateFollowUpError(Exception):
    """The most recent round already asked for exactly this same set of
    fields, and nothing has changed since — refuse to nag the supplier
    with an identical request."""


class MaxAutomaticRoundsReachedError(Exception):
    """Automatic follow-up has already run `max_automatic_follow_up_rounds`
    times for this request with information still missing — a human needs
    to take it from here (manual follow-up is never capped)."""


class RequestNotEligibleForFollowUpError(Exception):
    """Revoked, never sent, or otherwise not in a state a follow-up makes
    sense for."""


@dataclass(frozen=True)
class RecoveryStats:
    """The "information recovery rate" metric — see the FASE 6 spec's
    section 20. `total_requested`/`available_now` are always computed live;
    `available_after_first_submission` is the one value that can only come
    from a snapshot taken at the time (see `ComplianceRequest.
    fields_available_after_first_submission`), since `PackagingComponent`
    has no field-level history to reconstruct it from afterwards.
    """

    total_requested: int
    available_after_first_submission: int | None
    available_now: int
    follow_up_recovered: int | None

    @property
    def recovery_rate(self) -> float | None:
        if self.total_requested == 0:
            return None
        return self.available_now / self.total_requested


class FollowUpService:
    def __init__(self, db: Session, email_service: EmailService, settings: Settings | None = None):
        self.db = db
        self.email_service = email_service
        self.settings = settings or get_settings()
        self.round_repository = FollowUpRoundRepository(db)
        self.document_repository = SupplierDocumentRepository(db)
        self.audit_service = AuditService(db)
        self.missing_information_service = MissingInformationService(db)

    def _build_request_url(self, raw_token: str) -> str:
        return f"{self.settings.frontend_base_url}/request/{raw_token}"

    def _assert_can_follow_up(
        self, company: Company, request: ComplianceRequest, summary: RequestInformationSummary
    ) -> None:
        if request.token_revoked_at is not None or request.secure_token_hash is None:
            raise RequestNotEligibleForFollowUpError("This request has no active link")
        # Checked ahead of the (redundant, in practice) COMPLETED status
        # check: `summary.status` is the live, authoritative source of
        # truth for "is anything actually missing" — `NothingMissingError`
        # is the more specific, more useful error of the two.
        if summary.status == InformationStatus.COMPLETE:
            raise NothingMissingError("Nothing is missing for this request")
        if request.status == RequestStatus.COMPLETED.value:
            raise RequestNotEligibleForFollowUpError("This request is already complete")
        if any(
            doc.extraction_status == "processing"
            for doc in self.document_repository.list_for_request(request.id)
        ):
            raise ExtractionStillProcessingError("A document is still being processed")
        if summary.status in (InformationStatus.CONFLICT, InformationStatus.REVIEW_REQUIRED):
            raise ReviewRequiredBeforeFollowUpError(
                "Resolve pending extractions/conflicts before following up"
            )

        latest = self.round_repository.latest_for_request(company.id, request.id)
        if latest is not None:
            previous_refs = {(r["packaging_component_id"], r["field_name"]) for r in latest.requested_fields}
            current_refs = {
                (r["packaging_component_id"], r["field_name"]) for r in summary.missing_field_refs
            }
            if previous_refs == current_refs:
                raise DuplicateFollowUpError(
                    "The last follow-up already asked for exactly this information"
                )

    def _missing_information_email_context(
        self,
        company: Company,
        request: ComplianceRequest,
        summary: RequestInformationSummary,
        request_url: str,
    ) -> MissingInformationFollowUpEmailContext:
        component_names = {c.component_id: c.component_name for c in summary.components}
        missing_component_ids = {
            uuid.UUID(ref["packaging_component_id"]) for ref in summary.missing_field_refs
        }
        return MissingInformationFollowUpEmailContext(
            supplier_email=request.supplier.email,
            supplier_name=request.supplier.name,
            company_name=company.name,
            missing_fields=tuple(
                MissingFieldRef(
                    component_name=component_names[uuid.UUID(ref["packaging_component_id"])],
                    field_name=ref["field_name"],
                )
                for ref in summary.missing_field_refs
            ),
            request_url=request_url,
            language=request.language,
            multiple_components=len(missing_component_ids) > 1,
        )

    def _mint_token(self, request: ComplianceRequest) -> str:
        raw_token = generate_secure_token()
        request.secure_token_hash = hash_token(raw_token)
        request.token_expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.supplier_token_default_expiry_days
        )
        request.token_revoked_at = None
        return self._build_request_url(raw_token)

    def create_round(
        self,
        company: Company,
        actor_user_id: uuid.UUID | None,
        request: ComplianceRequest,
        trigger: str,
    ) -> FollowUpRound:
        summary = self.missing_information_service.summarize(company.id, request)
        self._assert_can_follow_up(company, request, summary)

        if trigger == "automatic":
            automatic_rounds = sum(
                1
                for r in self.round_repository.list_for_request(company.id, request.id)
                if r.trigger == "automatic"
            )
            if automatic_rounds >= self.settings.max_automatic_follow_up_rounds:
                raise MaxAutomaticRoundsReachedError(
                    f"Already sent {automatic_rounds} automatic follow-ups"
                )

        request_url = self._mint_token(request)
        email_context = self._missing_information_email_context(company, request, summary, request_url)
        self.email_service.send_missing_information_follow_up(email_context)

        round_number = len(self.round_repository.list_for_request(company.id, request.id)) + 1
        follow_up_round = FollowUpRound(
            company_id=company.id,
            request_id=request.id,
            round_number=round_number,
            requested_fields=summary.missing_field_refs,
            trigger=trigger,
            available_count_before=summary.available_count,
            missing_count_before=summary.missing_count,
            created_by_user_id=actor_user_id,
        )
        self.round_repository.add(follow_up_round)

        self.audit_service.record(
            company_id=company.id,
            event_type=AuditEventType.FOLLOW_UP_CREATED,
            entity_type="compliance_request",
            entity_id=request.id,
            actor_user_id=actor_user_id,
            metadata={
                "round_number": round_number,
                "trigger": trigger,
                "missing_count": summary.missing_count,
            },
        )
        return follow_up_round

    def reevaluate(
        self, company: Company, actor_user_id: uuid.UUID | None, request: ComplianceRequest
    ) -> ComplianceRequest:
        """Call after anything that can change completeness. Never raises —
        an automatic follow-up attempt that isn't currently possible (still
        processing, needs review, already asked, capped) just quietly waits
        for the next trigger or a human's manual click, except hitting the
        automatic-round cap, which is worth a durable audit trail entry."""
        summary = self.missing_information_service.summarize(company.id, request)

        # A request covering a product with zero PackagingComponents has
        # nothing to request in the first place — `total_requested == 0`
        # makes MissingInformationService's COMPLETE check vacuously true,
        # which would auto-complete (and email a "thank you, all done!") a
        # request that never actually tracked anything. Leave it exactly as
        # the caller (submit/accept/reject) already left it instead.
        if summary.total_requested == 0:
            return request

        if summary.status == InformationStatus.COMPLETE:
            if request.status != RequestStatus.COMPLETED.value:
                request.status = RequestStatus.COMPLETED.value
                request.completed_at = datetime.now(timezone.utc)
                self.db.flush()
                self.audit_service.record(
                    company_id=company.id,
                    event_type=AuditEventType.REQUEST_COMPLETED,
                    entity_type="compliance_request",
                    entity_id=request.id,
                    actor_user_id=actor_user_id,
                )
                self.email_service.send_request_complete(
                    RequestCompleteEmailContext(
                        supplier_email=request.supplier.email,
                        supplier_name=request.supplier.name,
                        company_name=company.name,
                        language=request.language,
                    )
                )
            return request

        if summary.status == InformationStatus.MISSING_INFORMATION and request.automatic_follow_up:
            try:
                self.create_round(company, None, request, trigger="automatic")
            except MaxAutomaticRoundsReachedError:
                self.audit_service.record(
                    company_id=company.id,
                    event_type=AuditEventType.REQUEST_NEEDS_HUMAN_ATTENTION,
                    entity_type="compliance_request",
                    entity_id=request.id,
                    metadata={"reason": "max_automatic_follow_up_rounds_reached"},
                )
            except (
                NothingMissingError,
                ExtractionStillProcessingError,
                ReviewRequiredBeforeFollowUpError,
                DuplicateFollowUpError,
                RequestNotEligibleForFollowUpError,
            ):
                pass
        return request

    def send_reminder(self, company: Company, request: ComplianceRequest) -> None:
        """A REMINDER is not a FOLLOW-UP — see this module's and
        `ReminderService`'s docstrings for why the two are kept distinct.
        Nothing new is being *asked*: this just re-delivers whatever is
        currently the live, correct email (the initial request if the
        supplier has never engaged, or the current missing-information ask
        if a follow-up round already exists) via a freshly minted token —
        no new `FollowUpRound` row, no `round_number` bump, since the
        content being resent hasn't changed.
        """
        request_url = self._mint_token(request)

        latest_round = self.round_repository.latest_for_request(company.id, request.id)
        if latest_round is None:
            self.email_service.send_compliance_request(
                ComplianceRequestEmailContext(
                    supplier_email=request.supplier.email,
                    supplier_name=request.supplier.name,
                    company_name=company.name,
                    number_of_products=len(request.products),
                    request_url=request_url,
                    language=request.language,
                )
            )
        else:
            summary = self.missing_information_service.summarize(company.id, request)
            email_context = self._missing_information_email_context(
                company, request, summary, request_url
            )
            self.email_service.send_missing_information_follow_up(email_context)
        self.audit_service.record(
            company_id=company.id,
            event_type=AuditEventType.EMAIL_RESENT,
            entity_type="compliance_request",
            entity_id=request.id,
            metadata={"reason": "reminder"},
        )

    def recovery_stats(self, company_id: uuid.UUID, request: ComplianceRequest) -> RecoveryStats:
        summary = self.missing_information_service.summarize(company_id, request)
        follow_up_recovered = None
        if request.fields_available_after_first_submission is not None:
            follow_up_recovered = (
                summary.available_count - request.fields_available_after_first_submission
            )
        return RecoveryStats(
            total_requested=summary.total_requested,
            available_after_first_submission=request.fields_available_after_first_submission,
            available_now=summary.available_count,
            follow_up_recovered=follow_up_recovered,
        )
