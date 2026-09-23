import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_kie_on_real_fir():
    sample_file_path = "samples/real_fir.jpg"
    print(f"Testing POST /extract/fir on real FIR image: {sample_file_path}")

    with open(sample_file_path, "rb") as f:
        files = {"file": ("real_fir.jpg", f, "image/jpeg")}
        response = client.post("/extract/fir", files=files)

    print(f"HTTP Status Code: {response.status_code}")
    assert response.status_code == 200, f"Error: {response.text}"

    data = response.json()
    print("\n================ FIR KIE EXTRACTION RESULT ================")
    print(json.dumps(data, indent=2))
    print("===========================================================\n")


if __name__ == "__main__":
    test_kie_on_real_fir()
