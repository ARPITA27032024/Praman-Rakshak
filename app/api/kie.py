from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from app.services.ocr import ocr_service
from app.services.fir_kie import fir_kie_service

router = APIRouter(tags=["Key Information Extraction"])


class FieldMetadata(BaseModel):
    value: Optional[str] = Field(None, description="Extracted text value for the target field.")
    confidence: float = Field(..., description="Confidence score associated with the extracted region.")
    bbox: list = Field(..., description="Bounding box [x1, y1, x2, y2] of the extracted field.")
    source: str = Field(default="ocr", description="Data source (e.g., 'ocr').")
    validation: str = Field(..., description="Validation status: 'valid', 'uncertain', or 'not_found'.")


class KIEResponse(BaseModel):
    success: bool
    filename: str
    extracted_fields: Dict[str, FieldMetadata]


@router.post("/extract/fir", response_model=KIEResponse, status_code=status.HTTP_200_OK)
async def extract_fir_key_information(file: UploadFile = File(...)):
    """
    Extract key structured fields (Police Station, Year, Statutes, Complainant Name)
    from an uploaded FIR document image or PDF with validation metadata.
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

        # 1. Run existing OCR service
        ocr_result = ocr_service.process_document(file_bytes, file.filename)
        ocr_regions = ocr_result.get("regions", [])

        # 2. Extract structured fields via KIE service
        fields = fir_kie_service.extract_fields(ocr_regions)

        return {
            "success": True,
            "filename": file.filename,
            "extracted_fields": fields,
        }

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during FIR KIE processing: {str(err)}"
        )
