import sys
import os
import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.redaction import redaction_service, RedactionService


class TestRedactionService(unittest.TestCase):

    def setUp(self):
        # Create a 200x200 white sample image in memory
        self.img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        img_bytes_io = io.BytesIO()
        self.img.save(img_bytes_io, format="PNG")
        self.img_bytes = img_bytes_io.getvalue()

    def test_bbox_rectangle_covered_and_same_dimensions(self):
        pii_entities = [
            {
                "type": "PERSON_NAME",
                "text": "Sensitive Name",
                "confidence": 0.90,
                "bbox": [50.0, 50.0, 100.0, 80.0],
                "page": 1,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "redacted_test.png")
            redaction_service._redact_image(
                self.img_bytes, pii_entities, out_file, padding=4
            )

            # 4. Check redacted image exists and has same dimensions
            self.assertTrue(os.path.exists(out_file))
            redacted_img = Image.open(out_file)
            self.assertEqual(redacted_img.size, (200, 200))

            # 1. Check pixels inside the bbox area are black (0, 0, 0)
            center_pixel = redacted_img.getpixel((75, 65))
            self.assertEqual(center_pixel, (0, 0, 0))

    def test_padding_works(self):
        pii_entities = [
            {
                "type": "PERSON_NAME",
                "text": "Secret",
                "confidence": 0.85,
                "bbox": [50.0, 50.0, 100.0, 80.0],
                "page": 1,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "redacted_padded.png")
            redaction_service._redact_image(
                self.img_bytes, pii_entities, out_file, padding=4
            )

            redacted_img = Image.open(out_file)
            # Padded pixel (50 - 2 = 48, 50 - 2 = 48) should be black
            padded_pixel = redacted_img.getpixel((48, 48))
            self.assertEqual(padded_pixel, (0, 0, 0))

            # Unpadded pixel (40, 40) outside padding should remain white
            outside_pixel = redacted_img.getpixel((40, 40))
            self.assertEqual(outside_pixel, (255, 255, 255))

    def test_bbox_clamped_to_image_boundaries(self):
        # Bbox extends beyond image dimensions (-20 to 250)
        bbox = [-20.0, -10.0, 250.0, 220.0]
        px1, py1, px2, py2 = RedactionService.pad_and_clamp_bbox(bbox, 200, 200, padding=4)

        self.assertEqual(px1, 0)
        self.assertEqual(py1, 0)
        self.assertEqual(px2, 200)
        self.assertEqual(py2, 200)

    def test_original_image_bytes_unchanged(self):
        original_bytes_copy = bytes(self.img_bytes)
        pii_entities = [
            {
                "type": "ADDRESS",
                "text": "123 Secret Street",
                "confidence": 0.80,
                "bbox": [10.0, 10.0, 50.0, 30.0],
                "page": 1,
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = os.path.join(tmp_dir, "redacted_copy.png")
            redaction_service._redact_image(
                self.img_bytes, pii_entities, out_file, padding=4
            )

        # Original source bytes must remain 100% identical
        self.assertEqual(self.img_bytes, original_bytes_copy)

    def test_unsupported_pii_type_ignored(self):
        pii_entities = [
            {
                "type": "CREDIT_CARD_UNSUPPORTED",
                "text": "411111111111",
                "confidence": 0.99,
                "bbox": [10.0, 10.0, 50.0, 30.0],
                "page": 1,
            }
        ]
        valid_ents, meta = redaction_service._filter_entities(pii_entities, confidence_threshold=0.60)
        self.assertEqual(len(valid_ents), 0)
        self.assertEqual(len(meta), 0)

    def test_low_confidence_pii_ignored(self):
        pii_entities = [
            {
                "type": "PERSON_NAME",
                "text": "Low Conf Name",
                "confidence": 0.40,  # Below 0.60 threshold
                "bbox": [10.0, 10.0, 50.0, 30.0],
                "page": 1,
            }
        ]
        valid_ents, meta = redaction_service._filter_entities(pii_entities, confidence_threshold=0.60)
        self.assertEqual(len(valid_ents), 0)
        self.assertEqual(len(meta), 0)

    def test_multiple_pii_regions_redacted(self):
        pii_entities = [
            {"type": "PERSON_NAME", "text": "Name 1", "confidence": 0.80, "bbox": [10, 10, 40, 40], "page": 1},
            {"type": "ADDRESS", "text": "Addr 2", "confidence": 0.75, "bbox": [60, 60, 90, 90], "page": 1},
        ]
        valid_ents, meta = redaction_service._filter_entities(pii_entities, confidence_threshold=0.60)
        self.assertEqual(len(valid_ents), 2)
        self.assertEqual(len(meta), 2)

    def test_metadata_does_not_contain_sensitive_text(self):
        pii_entities = [
            {
                "type": "PERSON_NAME",
                "text": "Confidential Name Rajesh",
                "confidence": 0.85,
                "bbox": [10.0, 10.0, 50.0, 30.0],
                "page": 1,
            }
        ]
        _, meta = redaction_service._filter_entities(pii_entities, confidence_threshold=0.60)
        self.assertEqual(len(meta), 1)
        # Check 'text' is NOT present anywhere in metadata dictionary
        self.assertNotIn("text", meta[0])
        self.assertIn("type", meta[0])
        self.assertIn("bbox", meta[0])
        self.assertIn("confidence", meta[0])

    def test_missing_or_invalid_bbox_handled_safely(self):
        invalid_entities = [
            {"type": "PERSON_NAME", "text": "No Bbox", "confidence": 0.90, "bbox": None, "page": 1},
            {"type": "ADDRESS", "text": "Zero Area", "confidence": 0.90, "bbox": [50, 50, 50, 50], "page": 1},
            {"type": "PHONE_NUMBER", "text": "Inv Area", "confidence": 0.90, "bbox": [50, 50, 30, 30], "page": 1},
        ]
        valid_ents, meta = redaction_service._filter_entities(invalid_entities, confidence_threshold=0.60)
        self.assertEqual(len(valid_ents), 0)
        self.assertEqual(len(meta), 0)


if __name__ == "__main__":
    unittest.main()
