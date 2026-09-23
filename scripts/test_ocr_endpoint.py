import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ocr():
    sample_file_path = "samples/sample_fir.png"
    print(f"Testing POST /ocr with sample image: {sample_file_path}")

    with open(sample_file_path, "rb") as f:
        files = {"file": ("sample_fir.png", f, "image/png")}
        response = client.post("/ocr", files=files)

    print(f"HTTP Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))

    assert response.status_code == 200
    assert response.json().get("success") is True
    print("\nSUCCESS: OCR endpoint test passed!")


if __name__ == "__main__":
    test_ocr()
