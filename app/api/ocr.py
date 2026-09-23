from fastapi import APIRouter, File, UploadFile, HTTPException, status
from app.services.ocr import ocr_service

router = APIRouter(tags=["OCR"])


@router.post("/ocr", status_code=status.HTTP_200_OK)
async def extract_text_from_document(file: UploadFile = File(...)):
    """
    Extract text and text regions with confidence scores from an uploaded document.
    Supported file types: JPG, JPEG, PNG, PDF.
    
    The original uploaded document is analyzed in memory and NEVER modified.
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

        result = ocr_service.process_document(file_bytes, file.filename)
        return result

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during OCR processing: {str(err)}"
        )
