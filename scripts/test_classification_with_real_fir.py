import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_real_fir_classification():
    file_path = "samples/real_fir.jpg"
    print(f"--- 1. Step 1: Extract OCR Text from {file_path} ---")

    with open(file_path, "rb") as f:
        files = {"file": ("real_fir.jpg", f, "image/jpeg")}
        ocr_response = client.post("/ocr", files=files)

    assert ocr_response.status_code == 200, f"OCR Error: {ocr_response.text}"
    ocr_data = ocr_response.json()
    extracted_text = ocr_data.get("text", "")
    print(f"Extracted {len(extracted_text)} characters of OCR text.")

    print("\n--- 2. Step 2: Send OCR Text to POST /classify ---")
    classify_response = client.post(
        "/classify",
        json={"text": extracted_text}
    )

    assert classify_response.status_code == 200, f"Classify Error: {classify_response.text}"
    result = classify_response.json()

    print("\n================ CLASSIFICATION RESULT ================")
    print(f"Predicted Document Type: {result['document_type']}")
    print(f"Confidence Score:        {result['confidence']}")
    print(f"Tags:                    {result['tags']}")
    print(f"Matched Indicators:      {result['matched_indicators']}")
    print("=======================================================\n")


if __name__ == "__main__":
    test_real_fir_classification()
