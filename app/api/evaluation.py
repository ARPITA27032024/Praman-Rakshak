from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from app.services.fir_dataset_evaluator import fir_evaluator

router = APIRouter(tags=["Evaluation"])


class EvaluateRequest(BaseModel):
    max_images: int = Field(default=10, ge=1, le=544, description="Maximum number of dataset images to evaluate.")


class EvaluateResponse(BaseModel):
    images_evaluated: int
    annotations_evaluated: int
    overall_exact_match: str
    overall_fuzzy_match: str
    average_confidence: float
    per_field_results: Dict[str, Any]
    unmatched_examples: List[Dict[str, Any]]


@router.post("/evaluate/fir-dataset", response_model=EvaluateResponse, status_code=status.HTTP_200_OK)
async def evaluate_fir_dataset(request: Optional[EvaluateRequest] = None):
    """
    Evaluate PaddleOCR field extraction accuracy against ground-truth ICDAR2023 FIR annotations.
    Processes up to max_images (default: 10) to optimize execution time.
    """
    max_images = request.max_images if request else 10

    try:
        results = fir_evaluator.evaluate(max_images=max_images)
        return results
    except FileNotFoundError as fnf_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(fnf_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error evaluating FIR dataset: {str(err)}"
        )
