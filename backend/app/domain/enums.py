"""Domain-level constants that are validated in Python, not enforced by a
native PostgreSQL enum type.

Convention (applies to this file and to whatever gets added in later
phases, e.g. `document_type` in FASE 4 or `entity_type` in FASE 7): a
native Postgres ENUM is reserved for values that are genuinely closed and
stable. Anything whose set of values is likely to grow while we're still
validating the product — `packaging_type` is the clearest example, but the
same reasoning will apply to `document_type` and extraction `entity_type`
once those tables exist — is stored as a plain VARCHAR column and validated
here / in Pydantic schemas instead. A native enum requires an `ALTER TYPE
... ADD VALUE` migration (and, in older Postgres versions, one that can't
run inside the same transaction as other changes) every time the set
grows; a VARCHAR + application-level validation needs a one-line code
change and no migration at all.

`ComplianceStatus` is different: it is never a database column at all (see
`StatusCalculationService`), only ever the return type of a computation, so
the enum-vs-varchar tradeoff doesn't apply to it — it lives here simply
because it's a shared domain type.
"""

from enum import Enum


class PackagingType(str, Enum):
    BOX = "box"
    BAG = "bag"
    LABEL = "label"
    FILLER = "filler"
    OUTER_ENVELOPE = "outer_envelope"
    OTHER = "other"


class ComplianceStatus(str, Enum):
    """Traffic-light status computed on the fly by StatusCalculationService —
    never cached on Product/PackagingComponent (see that service's
    docstring for why).
    """

    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


class Locale(str, Enum):
    """One shared type for two related uses, since they're the same concept:

    1. `ComplianceRequest.language` — the request/email/public supplier
       portal all speak the language the *supplier* works in, independent
       of the buyer company's own language: a Spanish company can have a
       supplier in Germany or China. Chosen explicitly by the company user
       per request, never inferred from the supplier's country.
    2. The Angular app's own locale switching (`frontend/src/app/core/i18n/`).

    Only ES/EN for now, matching the initial Spain-first go-to-market — not
    a statement that Sourcelya only ever supports two languages.
    """

    ES = "es"
    EN = "en"


class RequestStatus(str, Enum):
    """Stored as VARCHAR on `ComplianceRequest.status` (see this module's
    docstring for why) — a linear-with-a-loop state machine, advanced only
    by `ComplianceRequestService`/`PublicRequestService`, never set
    directly:

        DRAFT -> SENT -> OPENED -> IN_PROGRESS -> SUBMITTED -> COMPLETED
                            ^                         |
                            +---- follow-up round -----+
                              (back to IN_PROGRESS on the
                               supplier's next edit, then
                               SUBMITTED again)

    `COMPLETED` is only ever reached once `MissingInformationService`
    reports every requested field AVAILABLE with no pending review/conflict
    — see `ComplianceRequestService._reevaluate_completion` (FASE 6).
    Revocation is not a status here: it's the orthogonal
    `token_revoked_at`, unchanged since FASE 3.

    FASE 6 removed the previously-unused `REVIEW_REQUIRED` value: it would
    now collide in meaning with `InformationStatus.REVIEW_REQUIRED`, which
    is a computed, per-request concept (see `MissingInformationService`),
    never a stored workflow status.
    """

    DRAFT = "draft"
    SENT = "sent"
    OPENED = "opened"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class AuditEventType(str, Enum):
    """What gets recorded in `AuditEvent.event_type`. Expected to grow as
    later phases add more auditable actions (reminders, extracted-field
    decisions, ...) — VARCHAR, not a native enum, for the same reason as
    `PackagingType`.
    """

    REQUEST_CREATED = "request_created"
    REQUEST_SENT = "request_sent"
    REQUEST_OPENED = "request_opened"
    REQUEST_SAVED = "request_saved"
    REQUEST_SUBMITTED = "request_submitted"
    TOKEN_REVOKED = "token_revoked"
    EMAIL_RESENT = "email_resent"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    EXTRACTION_COMPLETED = "extraction_completed"
    EXTRACTION_FAILED = "extraction_failed"
    EXTRACTED_FIELD_ACCEPTED = "extracted_field_accepted"
    EXTRACTED_FIELD_REJECTED = "extracted_field_rejected"
    SUPPLIER_RESUBMITTED = "supplier_resubmitted"
    FOLLOW_UP_CREATED = "follow_up_created"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_NEEDS_HUMAN_ATTENTION = "request_needs_human_attention"


class DocumentType(str, Enum):
    """Business classification of a `SupplierDocument`. Minimal, useful
    categories only (see FASE 5 spec: "no crear una taxonomía enorme") —
    set automatically by `DocumentExtractionService` as part of the same
    call that extracts fields, never by a separate classifier or a manual
    picker in the upload form.
    """

    PACKAGING_SPECIFICATION = "packaging_specification"
    TECHNICAL_DATASHEET = "technical_datasheet"
    CERTIFICATE = "certificate"
    DECLARATION = "declaration"
    INVOICE_COMMERCIAL = "invoice_commercial"
    OTHER = "other"


class ExtractionStatus(str, Enum):
    """`SupplierDocument.extraction_status` — a small state machine advanced
    only by `ExtractionService` (FASE 5):

        PENDING -> PROCESSING -> COMPLETED
                                -> FAILED (retry moves back to PENDING)
                                -> REVIEW_REQUIRED (COMPLETED, but at least
                                   one field came back LOW confidence or with
                                   an unresolved conflict at accept time)

    A failed extraction never deletes or loses the original document — only
    this status column changes; `POST /api/documents/{id}/retry-extraction`
    re-attempts it.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class ConfidenceLevel(str, Enum):
    """How sure we are that an `ExtractedField` value is real, as a small
    closed set of categories rather than an unfounded percentage — see
    `app/services/extraction_service.py` module docstring for exactly how
    each level is derived (a deterministic rule, never a raw LLM-reported
    number taken at face value).
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FieldReviewStatus(str, Enum):
    """`ExtractedField.review_status` — sourced data never reaches
    `PackagingComponent` until a human explicitly decides. See
    `app/models/extracted_field.py`.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ExtractableFieldName(str, Enum):
    """The only fields FASE 5 ever proposes values for — deliberately just
    the `PackagingComponent` columns the product spec names, not a full
    PPWR field set. See `app/services/extraction_service.py`.

    FASE 6 reuses this exact set as the "requested fields" a
    `ComplianceRequest` expects back from a supplier — see
    `MissingInformationService`. Two different phases needing the same set
    of five fields is a sign they should stay the *same* enum, not fork
    into a parallel "RequestedFieldName".
    """

    PACKAGING_TYPE = "packaging_type"
    MATERIAL = "material"
    WEIGHT_GRAMS = "weight_grams"
    RECYCLED_CONTENT_PERCENTAGE = "recycled_content_percentage"
    PACKAGING_REFERENCE = "packaging_reference"


class FieldInformationState(str, Enum):
    """Per (packaging_component, field_name) classification computed by
    `MissingInformationService` (FASE 6) — never stored, never inferred by
    an LLM. See that service's module docstring for the exact deterministic
    rule behind each value.

    `NOT_APPLICABLE` is defined because the FASE 6 spec explicitly asks the
    model to be *able* to distinguish it, but nothing produces it yet — no
    field-applicability-by-packaging-type rule exists (that would be the
    start of a legal rules engine, explicitly out of scope). Documented as
    a limitation, not silently dropped.
    """

    AVAILABLE = "available"
    MISSING = "missing"
    REVIEW_REQUIRED = "review_required"
    CONFLICT = "conflict"
    NOT_APPLICABLE = "not_applicable"


class InformationStatus(str, Enum):
    """Request-level rollup of every field's `FieldInformationState`,
    computed by `MissingInformationService` — the ONLY thing Sourcelya is
    allowed to assert about a request's data in FASE 6 (see the spec's
    "PRINCIPIO FUNDAMENTAL": never "PPWR compliant"/"non-compliant", only
    these four). Never a stored column — same computed-not-cached pattern
    as `ComplianceStatus`. Priority when multiple fields disagree:
    CONFLICT > REVIEW_REQUIRED > MISSING_INFORMATION > COMPLETE.
    """

    COMPLETE = "complete"
    MISSING_INFORMATION = "missing_information"
    REVIEW_REQUIRED = "review_required"
    CONFLICT = "conflict"
