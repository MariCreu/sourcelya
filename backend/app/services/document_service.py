import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.domain.enums import AuditEventType, RequestStatus
from app.integrations.storage.base import StorageService
from app.models.compliance_request import ComplianceRequest
from app.models.supplier_document import SupplierDocument
from app.repositories.supplier_document_repository import SupplierDocumentRepository
from app.services.audit_service import AuditService

# Sourcelya's own canonical MIME type per allowed extension — used both to
# validate an upload and, crucially, to decide the Content-Type served back
# on download. A client-declared Content-Type is only trusted enough to be
# *checked* against this table, never stored or replayed as-is: serving
# back whatever a browser claimed a file was (e.g. "text/html") would be a
# stored-content-type footgun on download.
EXTENSION_MIME_TYPES: dict[str, tuple[str, frozenset[str]]] = {
    "pdf": ("application/pdf", frozenset({"application/pdf"})),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
    ),
    "csv": ("text/csv", frozenset({"text/csv", "application/vnd.ms-excel", "text/plain"})),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ),
    "png": ("image/png", frozenset({"image/png"})),
    "jpg": ("image/jpeg", frozenset({"image/jpeg"})),
    "jpeg": ("image/jpeg", frozenset({"image/jpeg"})),
}

# Some browsers/HTTP clients send this instead of a real content type —
# tolerated as long as the extension itself is on the allow-list.
_GENERIC_CONTENT_TYPES = {"application/octet-stream", ""}


@dataclass(frozen=True)
class UploadedFilePayload:
    """Plain data the API layer extracts from FastAPI's `UploadFile` before
    calling into the service — keeps the service layer free of any
    framework-specific request type, matching this codebase's convention
    of services taking plain data/Pydantic schemas, never FastAPI objects.
    """

    filename: str
    content_type: str
    content: bytes


class UnsupportedFileTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


class RequestNotEditableError(Exception):
    """Raised when trying to upload/delete a document on a request that has
    already been submitted — see the FASE 4 spec's "subir y eliminar antes
    de submit"."""


class DocumentNotFoundError(Exception):
    pass


def _extension_of(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


class DocumentService:
    def __init__(self, db: Session, storage: StorageService, settings: Settings | None = None):
        self.db = db
        self.storage = storage
        self.repository = SupplierDocumentRepository(db)
        self.audit_service = AuditService(db)
        self.settings = settings or get_settings()

    def _validate(self, upload: UploadedFilePayload) -> str:
        extension = _extension_of(upload.filename)
        if extension not in self.settings.allowed_upload_extensions:
            raise UnsupportedFileTypeError(f"'.{extension}' files are not accepted")

        canonical_content_type, accepted_content_types = EXTENSION_MIME_TYPES[extension]
        declared = upload.content_type.lower()
        if declared not in _GENERIC_CONTENT_TYPES and declared not in accepted_content_types:
            raise UnsupportedFileTypeError(
                f"Content-Type '{upload.content_type}' does not match a '.{extension}' file"
            )

        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(upload.content) > max_bytes:
            raise FileTooLargeError(
                f"File exceeds the {self.settings.max_upload_size_mb}MB limit"
            )

        return canonical_content_type

    def upload_for_request(
        self, request: ComplianceRequest, upload: UploadedFilePayload
    ) -> SupplierDocument:
        # FASE 6: SUBMITTED no longer blocks new uploads — a supplier may
        # attach more documents during a follow-up round (see
        # PublicRequestService's updated docstring/RequestStatus). Only
        # COMPLETED is truly terminal.
        if request.status == RequestStatus.COMPLETED.value:
            raise RequestNotEditableError("This request has already been completed")

        canonical_content_type = self._validate(upload)
        extension = _extension_of(upload.filename)
        document_id = uuid.uuid4()
        storage_path = (
            f"companies/{request.company_id}/requests/{request.id}/{document_id}.{extension}"
        )
        self.storage.upload(path=storage_path, content=upload.content, content_type=canonical_content_type)

        document = SupplierDocument(
            id=document_id,
            company_id=request.company_id,
            supplier_id=request.supplier_id,
            request_id=request.id,
            filename=upload.filename,
            storage_path=storage_path,
            content_type=canonical_content_type,
            size_bytes=len(upload.content),
        )
        self.db.add(document)
        self.db.flush()
        self.audit_service.record(
            company_id=request.company_id,
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            entity_type="supplier_document",
            entity_id=document.id,
            metadata={"request_id": str(request.id), "filename": upload.filename},
        )
        return document

    def delete_for_request(self, request: ComplianceRequest, document_id: uuid.UUID) -> None:
        if request.status == RequestStatus.COMPLETED.value:
            raise RequestNotEditableError("This request has already been completed")

        document = self.repository.get_for_request(request.id, document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found on this request")

        self.storage.delete(path=document.storage_path)
        self.db.delete(document)
        self.db.flush()
        self.audit_service.record(
            company_id=request.company_id,
            event_type=AuditEventType.DOCUMENT_DELETED,
            entity_type="supplier_document",
            entity_id=document_id,
            metadata={"request_id": str(request.id), "filename": document.filename},
        )

    def get_for_download(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> tuple[SupplierDocument, bytes] | None:
        document = self.repository.get(company_id, document_id)
        if document is None:
            return None
        return document, self.storage.download(path=document.storage_path)
