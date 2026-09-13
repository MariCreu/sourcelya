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
    docstring for why) — a linear state machine, advanced only by
    `ComplianceRequestService`/`PublicRequestService`, never set directly:

        DRAFT -> SENT -> OPENED -> IN_PROGRESS -> SUBMITTED

    `REVIEW_REQUIRED` and `COMPLETED` exist as states a later phase can move
    a request into (once there's a reason to — conflicting/low-confidence
    data, a company explicitly marking a request done) but nothing in FASE 3
    transitions a request into either yet.
    """

    DRAFT = "draft"
    SENT = "sent"
    OPENED = "opened"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEW_REQUIRED = "review_required"
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


class DocumentType(str, Enum):
    """Business classification of a `SupplierDocument`. FASE 4 has no UI or
    logic that ever sets anything other than `OTHER` — there is no document
    classifier yet (that's FASE 7's `DocumentExtractionService`) and no type
    picker in the upload form, on purpose (see the product spec's explicit
    "no clasificación automática todavía"). The column and this enum exist
    now so a future classifier has somewhere to write its answer without a
    schema change.
    """

    OTHER = "other"


class ExtractionStatus(str, Enum):
    """`SupplierDocument.extraction_status`. Every document is created with
    `PENDING` and nothing moves it out of that state until FASE 7 wires up
    a real `DocumentExtractionService` implementation — see that module's
    docstring. Deliberately only one member for now rather than
    pre-declaring FASE 7's states speculatively.
    """

    PENDING = "pending"
