import enum


class ComplianceStatus(str, enum.Enum):
    """Shared traffic-light status used by both PackagingComponent and Product.

    GREEN: all MVP-required fields present.
    ORANGE: some required fields are missing.
    RED: conflicting or low-confidence data needs human review.
    """

    GREEN = "green"
    ORANGE = "orange"
    RED = "red"


class RequestStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    OPENED = "opened"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEW_REQUIRED = "review_required"
    COMPLETED = "completed"


class PackagingType(str, enum.Enum):
    BOX = "box"
    BAG = "bag"
    LABEL = "label"
    FILLER = "filler"
    OUTER_ENVELOPE = "outer_envelope"
    OTHER = "other"


class DocumentType(str, enum.Enum):
    SPEC_SHEET = "spec_sheet"
    TEST_REPORT = "test_report"
    CERTIFICATE = "certificate"
    INVOICE = "invoice"
    PHOTO = "photo"
    OTHER = "other"


class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractedFieldEntityType(str, enum.Enum):
    PACKAGING_COMPONENT = "packaging_component"
    PRODUCT = "product"


class AuditEventType(str, enum.Enum):
    REQUEST_CREATED = "request_created"
    REQUEST_SENT = "request_sent"
    REQUEST_OPENED = "request_opened"
    DOCUMENT_UPLOADED = "document_uploaded"
    REQUEST_SUBMITTED = "request_submitted"
    FIELD_ACCEPTED = "field_accepted"
    FIELD_EDITED = "field_edited"
    REMINDER_SENT = "reminder_sent"
