import os
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, File, UploadFile, Query, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app.config import settings
from app.services.ocr import ocr_service
from app.services.fir_kie import fir_kie_service
from app.services.pii_detector import pii_detector_service
from app.services.redaction import redaction_service

router = APIRouter(tags=["PII Redaction"])


class RedactionMetadataItem(BaseModel):
    type: str = Field(..., description="Redacted PII category.")
    bbox: list = Field(..., description="Bounding box [x1, y1, x2, y2] that was redacted.")
    page: int = Field(default=1, description="Page number of the redacted region.")
    confidence: float = Field(..., description="Confidence score of the PII entity.")


class RedactionResponse(BaseModel):
    success: bool
    original_filename: str
    redacted_filename: str
    redacted_file_url: str
    redaction_count: int
    redactions: List[RedactionMetadataItem]


@router.post("/redact/pii", response_model=RedactionResponse, status_code=status.HTTP_200_OK)
async def redact_pii_document(
    file: UploadFile = File(...),
    confidence_threshold: float = Query(default=0.60, ge=0.0, le=1.0, description="Minimum PII confidence threshold to apply redaction."),
    padding: int = Query(default=4, ge=0, le=50, description="Padding pixels added around bounding box boundaries."),
):
    """
    Process an uploaded document through the complete pipeline (OCR -> KIE -> PII Detection -> Redaction)
    and save a separate redacted COPY of the document.
    
    The original uploaded file is NEVER modified or overwritten.
    Redaction metadata explicitly EXCLUDES sensitive original text.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename."
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        # 1. OCR Step
        ocr_result = ocr_service.process_document(file_bytes, file.filename)
        ocr_regions = ocr_result.get("regions", [])

        # 2. KIE Step
        kie_fields = fir_kie_service.extract_fields(ocr_regions)

        # 3. PII Detection Step
        pii_entities = pii_detector_service.detect_pii(ocr_regions, kie_fields)

        # 4. Redaction Step (Creates a separate redacted file in storage/redacted/)
        redact_res = redaction_service.redact_document(
            file_bytes=file_bytes,
            filename=file.filename,
            pii_entities=pii_entities,
            confidence_threshold=confidence_threshold,
            padding=padding,
        )

        redacted_filename = redact_res["redacted_filename"]
        redacted_url = f"/download/redacted/{redacted_filename}"

        return {
            "success": True,
            "original_filename": file.filename,
            "redacted_filename": redacted_filename,
            "redacted_file_url": redacted_url,
            "redaction_count": redact_res["redaction_count"],
            "redactions": redact_res["redactions"],
        }

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during PII redaction: {str(err)}"
        )


@router.get("/download/redacted/{filename}", response_class=FileResponse, tags=["PII Redaction"])
async def download_redacted_file(filename: str):
    """
    Download a previously created redacted document file from storage/redacted/.
    """
    file_path = Path(settings.REDACTED_DIR) / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Redacted file '{filename}' not found."
        )

    media_type = "application/pdf" if filename.endswith(".pdf") else "image/png"
    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)
