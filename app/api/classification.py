from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List
from app.services.classification import classifier_service


class ClassifyRequest(BaseModel):
    text: str = Field(..., description="OCR-extracted text of the document to classify.")


class ClassifyResponse(BaseModel):
    document_type: str = Field(..., description="Categorized document type (e.g., FIR, Charge Sheet, Medical Report).")
    confidence: float = Field(..., description="Meaningfully calculated rule-matching confidence score (0.0 to 1.0).")
    tags: List[str] = Field(..., description="Metadata tags associated with the document type.")
    matched_indicators: List[str] = Field(..., description="Specific text indicators/keywords detected in the text.")


router = APIRouter(tags=["Classification"])


@router.post("/classify", response_model=ClassifyResponse, status_code=status.HTTP_200_OK)
async def classify_document_text(request: ClassifyRequest):
    """
    Classify document text and return category, confidence score, tags, and matched indicators.
    Uses transparent, explainable structural indicator matching.
    """
    if not request.text or not request.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document text cannot be empty."
        )

    result = classifier_service.classify_text(request.text)
    return result
