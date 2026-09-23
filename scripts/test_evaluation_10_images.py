import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_full_system_and_evaluator():
    print("=== 1. Test GET /health ===")
    health_res = client.get("/health")
    print("Health Status Code:", health_res.status_code)
    print("Health Response:", health_res.json())
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    print("\n=== 2. Test POST /ocr ===")
    sample_file_path = "samples/sample_fir.png"
    with open(sample_file_path, "rb") as f:
        files = {"file": ("sample_fir.png", f, "image/png")}
        ocr_res = client.post("/ocr", files=files)
    print("OCR Status Code:", ocr_res.status_code)
    ocr_data = ocr_res.json()
    print("OCR Success:", ocr_data.get("success"))
    print("OCR Region Sample (with bbox):", ocr_data.get("regions", [])[0])
    assert ocr_res.status_code == 200
    assert ocr_data["success"] is True

    print("\n=== 3. Test POST /evaluate/fir-dataset (10 images) ===")
    eval_res = client.post("/evaluate/fir-dataset", json={"max_images": 10})
    print("Evaluation Status Code:", eval_res.status_code)
    eval_data = eval_res.json()
    print("\n================ EVALUATION SUMMARY ================")
    print(json.dumps(eval_data, indent=2))
    print("====================================================")
    assert eval_res.status_code == 200
    assert eval_data["images_evaluated"] > 0


if __name__ == "__main__":
    test_full_system_and_evaluator()
