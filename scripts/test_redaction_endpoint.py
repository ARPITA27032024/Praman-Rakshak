import sys
import os
import json
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_pii_redaction_endpoint():
    sample_file_path = "samples/real_fir.jpg"
    print(f"=== 1. Starting PII Redaction Endpoint Test on: {sample_file_path} ===")

    # Verify original file exists and record file modification time / size
    assert os.path.exists(sample_file_path), "Error: Original sample file does not exist."
    orig_stat = os.stat(sample_file_path)
    orig_mtime = orig_stat.st_mtime
    orig_size = orig_stat.st_size
    orig_img = Image.open(sample_file_path)
    orig_width, orig_height = orig_img.size
    print(f"Original file dimensions: {orig_width}x{orig_height} pixels | Size: {orig_size} bytes")

    # Send POST /redact/pii request
    with open(sample_file_path, "rb") as f:
        files = {"file": ("real_fir.jpg", f, "image/jpeg")}
        response = client.post("/redact/pii", files=files)

    print(f"HTTP Status Code: {response.status_code}")
    assert response.status_code == 200, f"Error: {response.text}"

    data = response.json()
    print("\n================ REDACTION METADATA RESPONSE ================")
    print(json.dumps(data, indent=2))
    print("============================================================\n")

    # Verify redacted file was created
    redacted_filename = data.get("redacted_filename")
    redacted_path = os.path.join("./storage/redacted", redacted_filename)
    print(f"=== 2. Verifying Redacted File Creation: {redacted_path} ===")
    assert os.path.exists(redacted_path), f"Error: Redacted output file missing at {redacted_path}"
    print(f"SUCCESS: Redacted output file exists at {redacted_path}")

    # Verify redacted file dimensions match original
    redacted_img = Image.open(redacted_path)
    red_width, red_height = redacted_img.size
    print(f"Redacted file dimensions: {red_width}x{red_height} pixels")
    assert (orig_width, orig_height) == (red_width, red_height), "Error: Dimensions do not match!"

    # Verify pixels inside detected PII bboxes are covered (black)
    redactions = data.get("redactions", [])
    print(f"\n=== 3. Verifying Black Rectangle Coverage on {len(redactions)} Redacted BBoxes ===")
    for idx, red in enumerate(redactions, 1):
        x1, y1, x2, y2 = red["bbox"]
        cx = int((x1 + x2) / 2)
        cy = int((y1 + y2) / 2)
        pixel = redacted_img.getpixel((cx, cy))
        print(f"BBox {idx} ({red['type']}) Center ({cx}, {cy}) Pixel RGB: {pixel}")
        assert pixel == (0, 0, 0), f"Error: BBox {idx} pixel is not black!"

    # Verify original file was NOT modified
    print("\n=== 4. Confirming Original Image Integrity ===")
    current_stat = os.stat(sample_file_path)
    assert current_stat.st_mtime == orig_mtime, "Error: Original file modification time changed!"
    assert current_stat.st_size == orig_size, "Error: Original file size changed!"
    print("CONFIRMED: Original sample image was NOT modified or altered in any way!")


if __name__ == "__main__":
    test_pii_redaction_endpoint()
