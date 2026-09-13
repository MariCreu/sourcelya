import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_db, get_storage_service
from app.integrations.storage.base import StorageService
from app.models.company import Company
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def _safe_filename(filename: str) -> str:
    """Strips characters that could break the Content-Disposition header
    (quotes, CR/LF) — the filename is company-controlled data by the time
    it reaches here, but nothing downstream should have to trust that."""
    return filename.replace('"', "'").replace("\r", "").replace("\n", "")


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    result = DocumentService(db, storage).get_for_download(company.id, document_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document, content = result
    return Response(
        content=content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(document.filename)}"'
        },
    )
