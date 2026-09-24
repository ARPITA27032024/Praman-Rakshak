import unittest
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app


class TestProcessEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Create a small valid test image in memory
        img = Image.new("RGB", (100, 100), color="white")
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format="JPEG")
        self.valid_img_bytes = img_byte_arr.getvalue()

    def test_process_document_success(self):
        response = self.client.post(
            "/process",
            files={"file": ("test_doc.jpg", self.valid_img_bytes, "image/jpeg")}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertIn("document_type", data)
        self.assertIn("confidence", data)
        self.assertIn("extracted_fields", data)
        self.assertIn("pii_entities", data)
        self.assertIn("redaction_count", data)
        self.assertIn("redaction_count", data)
        self.assertIn("redactions", data)
        self.assertIn("redacted_file_url", data)

    def test_process_document_invalid_extension(self):
        response = self.client.post(
            "/process",
            files={"file": ("test_doc.txt", b"some text content", "text/plain")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported file format", response.json()["detail"])

    def test_process_document_empty_file(self):
        response = self.client.post(
            "/process",
            files={"file": ("test_doc.jpg", b"", "image/jpeg")}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
