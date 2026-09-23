import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_real_fir():
    file_path = "samples/real_fir.jpg"
    print(f"--- Processing Real Scanned FIR Document: {file_path} ---")

    with open(file_path, "rb") as f:
        files = {"file": ("real_fir.jpg", f, "image/jpeg")}
        response = client.post("/ocr", files=files)

    assert response.status_code == 200, f"Error: {response.text}"
    data = response.json()

    print("\n=== EXTRACTED FULL TEXT ===")
    print(data.get("text", ""))
    print("============================\n")

    print("=== DETECTED REGIONS & CONFIDENCE SCORES ===")
    regions = data.get("regions", [])
    for idx, reg in enumerate(regions, 1):
        text = reg["text"]
        conf = reg["confidence"]
        print(f"{idx:02d}. [Confidence: {conf:.4f}] {text}")
    print(f"\nTotal regions detected: {len(regions)}")


if __name__ == "__main__":
    test_real_fir()
