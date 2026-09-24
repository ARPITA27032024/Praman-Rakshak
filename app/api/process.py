import logging
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel, Field

from app.services.ocr import ocr_service
from app.services.classification import classifier_service
from app.services.fir_kie import fir_kie_service
from app.services.pii_detector import pii_detector_service
from app.services.redaction import redaction_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Unified Processing"])

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}


class ProcessResponse(BaseModel):
    success: bool
    document_type: str = Field(..., description="Categorized document type (e.g. FIR).")
    confidence: float = Field(..., description="Classification confidence score.")
    extracted_fields: Dict[str, Any] = Field(..., description="KIE extracted structured fields.")
    pii_entities: List[Dict[str, Any]] = Field(..., description="List of detected PII entities.")
    redaction_count: int = Field(..., description="Total number of PII redactions applied.")
    redactions: List[Dict[str, Any]] = Field(..., description="List of redaction metadata objects.")
    redacted_file_url: str = Field(..., description="URL to download/preview redacted document.")
    redacted_filename: str = Field(..., description="Filename of created redacted document.")


@router.post("/process", response_model=ProcessResponse, status_code=status.HTTP_200_OK)
async def process_document_pipeline(file: UploadFile = File(...)):
    """
    Unified Single-Endpoint Document Processing Pipeline:
    Upload -> OCR -> Classification -> KIE -> PII Detection -> Redaction.
    Returns complete document intelligence payload in one call.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename."
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Supported formats: PNG, JPG, JPEG, PDF."
        )

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        logger.info("[PROCESS] upload received: %s (%d bytes)", file.filename, len(file_bytes))

        # 1. OCR Stage
        logger.info("[PROCESS] OCR started")
        ocr_result = ocr_service.process_document(file_bytes, file.filename)
        ocr_regions = ocr_result.get("regions", [])
        ocr_text = ocr_result.get("text", "")
        logger.info("[PROCESS] OCR completed (%d regions detected)", len(ocr_regions))

        # 2. Document Classification Stage
        logger.info("[PROCESS] classification started")
        classify_res = classifier_service.classify_text(ocr_text)
        doc_type = classify_res.get("document_type", "Unknown")
        doc_conf = classify_res.get("confidence", 0.0)
        logger.info("[PROCESS] classification completed (type: %s, conf: %.2f)", doc_type, doc_conf)

        # 3. Key Information Extraction Stage
        logger.info("[PROCESS] KIE started")
        kie_fields = fir_kie_service.extract_fields(ocr_regions)
        logger.info("[PROCESS] KIE completed (%d fields extracted)", len(kie_fields))

        # 4. PII Detection Stage
        logger.info("[PROCESS] PII detection started")
        pii_entities = pii_detector_service.detect_pii(ocr_regions, kie_fields)
        logger.info("[PROCESS] PII detection completed (%d PII entities found)", len(pii_entities))

        # 5. Redaction Stage
        logger.info("[PROCESS] redaction started")
        redact_res = redaction_service.redact_document(
            file_bytes=file_bytes,
            filename=file.filename,
            pii_entities=pii_entities,
            confidence_threshold=0.60,
            padding=4,
        )
        redact_count = redact_res.get("redaction_count", 0)
        redacted_filename = redact_res.get("redacted_filename", "")
        redacted_url = f"/download/redacted/{redacted_filename}"
        logger.info("[PROCESS] redaction completed (%d redactions applied)", redact_count)

        return {
            "success": True,
            "document_type": doc_type,
            "confidence": doc_conf,
            "extracted_fields": kie_fields,
            "pii_entities": pii_entities,
            "redaction_count": redact_count,
            "redactions": redact_res.get("redactions", []),
            "redacted_file_url": redacted_url,
            "redacted_filename": redacted_filename,
        }

    except ValueError as val_err:
        logger.warning("[PROCESS] Validation failure: %s", str(val_err))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error("[PROCESS] Unexpected pipeline error: %s", str(err), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing error: {str(err)}"
        )
    finally:
        import gc
        gc.collect()
