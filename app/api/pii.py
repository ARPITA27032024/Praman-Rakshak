from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from app.services.ocr import ocr_service
from app.services.fir_kie import fir_kie_service
from app.services.pii_detector import pii_detector_service

router = APIRouter(tags=["PII Detection"])


class PIIEntity(BaseModel):
    type: str = Field(..., description="PII Entity category (e.g., PERSON_NAME, ADDRESS, PHONE_NUMBER).")
    text: str = Field(..., description="Exact OCR text of the detected PII entity.")
    confidence: float = Field(..., description="Explainable confidence score (0.0 to 1.0).")
    bbox: list = Field(..., description="Bounding box [x1, y1, x2, y2] of the PII entity.")
    page: int = Field(default=1, description="Page number where entity was detected.")
    source: str = Field(default="ocr", description="Data source (e.g., 'ocr').")
    detection_method: str = Field(..., description="Detection method ('kie_context', 'label_context', 'regex', 'spatial_context').")


class PIIResponse(BaseModel):
    success: bool
    pii_entities: List[PIIEntity]


@router.post("/detect/pii", response_model=PIIResponse, status_code=status.HTTP_200_OK)
async def detect_pii_entities(file: UploadFile = File(...)):
    """
    Detect PII entities (names, addresses, phone numbers, emails, DOB, IDs)
    from an uploaded document image or PDF.
    
    Pipeline: Upload -> PaddleOCR -> FIR KIE -> PII Detector.
    Original uploaded file remains 100% unchanged.
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

        # 1. Reuse existing OCR service
        ocr_result = ocr_service.process_document(file_bytes, file.filename)
        ocr_regions = ocr_result.get("regions", [])

        # 2. Reuse existing KIE service
        kie_fields = fir_kie_service.extract_fields(ocr_regions)

        # 3. Run PII Detection
        pii_entities = pii_detector_service.detect_pii(ocr_regions, kie_fields)

        return {
            "success": True,
            "pii_entities": pii_entities,
        }

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during PII detection: {str(err)}"
        )
