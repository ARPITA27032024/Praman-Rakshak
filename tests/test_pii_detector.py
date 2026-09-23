import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.pii_detector import pii_detector_service, PIIDetector


class TestPIIDetector(unittest.TestCase):

    def setUp(self):
        self.detector = PIIDetector()

    def test_person_name_from_kie_context(self):
        ocr_regions = [
            {"text": "Saesmita choth.", "confidence": 0.7713, "bbox": [88, 306, 261, 344], "page": 1}
        ]
        kie_fields = {
            "complainant_name": {
                "value": "Saesmita choth.",
                "confidence": 0.7713,
                "bbox": [88, 306, 261, 344],
                "source": "ocr",
                "validation": "valid",
            }
        }
        entities = self.detector.detect_pii(ocr_regions, kie_fields)
        names = [e for e in entities if e["type"] == "PERSON_NAME"]
        self.assertGreaterEqual(len(names), 1)
        self.assertEqual(names[0]["text"], "Saesmita choth.")  # Text is NOT modified
        self.assertEqual(names[0]["detection_method"], "kie_context")
        self.assertEqual(names[0]["bbox"], [88, 306, 261, 344])

    def test_phone_number_detection(self):
        ocr_regions = [
            {"text": "Contact Mobile: +91-9876543210", "confidence": 0.95, "bbox": [10, 10, 150, 30], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        phones = [e for e in entities if e["type"] == "PHONE_NUMBER"]
        self.assertEqual(len(phones), 1)
        self.assertIn("9876543210", phones[0]["text"])

    def test_email_detection(self):
        ocr_regions = [
            {"text": "Email: officer.rajesh@police.gov.in", "confidence": 0.96, "bbox": [10, 10, 200, 30], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        emails = [e for e in entities if e["type"] == "EMAIL"]
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]["text"], "officer.rajesh@police.gov.in")

    def test_address_with_nearby_label(self):
        ocr_regions = [
            {"text": "Address:", "confidence": 0.99, "bbox": [10, 10, 80, 30], "page": 1},
            {"text": "1081, South Kodalia, P.O+P/S- Neco Banackporce, K0O-131", "confidence": 0.74, "bbox": [90, 10, 300, 30], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        addrs = [e for e in entities if e["type"] == "ADDRESS"]
        self.assertGreaterEqual(len(addrs), 1)
        self.assertIn("South Kodalia", addrs[0]["text"])

    def test_dob_only_with_dob_context(self):
        ocr_regions_with_dob = [
            {"text": "D.O.B. 15/08/1990", "confidence": 0.92, "bbox": [10, 10, 100, 30], "page": 1}
        ]
        ocr_regions_without_dob = [
            {"text": "Incident Date 15/08/1990", "confidence": 0.92, "bbox": [10, 10, 100, 30], "page": 1}
        ]

        dob_entities = self.detector.detect_pii(ocr_regions_with_dob)
        non_dob_entities = self.detector.detect_pii(ocr_regions_without_dob)

        self.assertEqual(len([e for e in dob_entities if e["type"] == "DATE_OF_BIRTH"]), 1)
        self.assertEqual(len([e for e in non_dob_entities if e["type"] == "DATE_OF_BIRTH"]), 0)

    def test_id_number_only_with_id_context(self):
        ocr_regions_with_id = [
            {"text": "Aadhaar ID No: 1234-5678-9012", "confidence": 0.90, "bbox": [10, 10, 150, 30], "page": 1}
        ]
        ocr_regions_without_id = [
            {"text": "GD Entry Number 1234-5678-9012", "confidence": 0.90, "bbox": [10, 10, 150, 30], "page": 1}
        ]

        id_entities = self.detector.detect_pii(ocr_regions_with_id)
        non_id_entities = self.detector.detect_pii(ocr_regions_without_id)

        self.assertEqual(len([e for e in id_entities if e["type"] == "ID_NUMBER"]), 1)
        self.assertEqual(len([e for e in non_id_entities if e["type"] == "ID_NUMBER"]), 0)

    def test_rejection_of_ordinary_fir_numbers(self):
        ocr_regions = [
            {"text": "FIR No: 4021/2026", "confidence": 0.95, "bbox": [10, 10, 100, 30], "page": 1},
            {"text": "GD No 14008", "confidence": 0.99, "bbox": [10, 40, 100, 60], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        phones = [e for e in entities if e["type"] == "PHONE_NUMBER"]
        ids = [e for e in entities if e["type"] == "ID_NUMBER"]
        self.assertEqual(len(phones), 0)
        self.assertEqual(len(ids), 0)

    def test_rejection_of_statute_numbers_as_phone_or_id(self):
        ocr_regions = [
            {"text": "Sections 341/354/354(B)", "confidence": 0.88, "bbox": [10, 10, 150, 30], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        phones = [e for e in entities if e["type"] == "PHONE_NUMBER"]
        ids = [e for e in entities if e["type"] == "ID_NUMBER"]
        self.assertEqual(len(phones), 0)
        self.assertEqual(len(ids), 0)

    def test_bounding_box_preservation(self):
        ocr_regions = [
            {"text": "Email: user@example.com", "confidence": 0.99, "bbox": [12.5, 34.0, 150.0, 56.5], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["bbox"], [12.5, 34.0, 150.0, 56.5])

    def test_ocr_text_is_never_modified(self):
        noisy_ocr_text = "Saesmita choth."
        ocr_regions = [
            {"text": noisy_ocr_text, "confidence": 0.7713, "bbox": [88, 306, 261, 344], "page": 1}
        ]
        kie_fields = {
            "complainant_name": {
                "value": noisy_ocr_text,
                "confidence": 0.7713,
                "bbox": [88, 306, 261, 344],
                "source": "ocr",
                "validation": "valid",
            }
        }
        entities = self.detector.detect_pii(ocr_regions, kie_fields)
        self.assertEqual(entities[0]["text"], noisy_ocr_text)

    def test_missing_fields_and_empty_regions(self):
        entities = self.detector.detect_pii([])
        self.assertEqual(len(entities), 0)

    def test_low_confidence_ocr_confidence_preservation(self):
        low_conf = 0.42
        ocr_regions = [
            {"text": "Address: Low Conf Street", "confidence": low_conf, "bbox": [10, 10, 100, 30], "page": 1}
        ]
        entities = self.detector.detect_pii(ocr_regions)
        self.assertGreaterEqual(len(entities), 1)
        self.assertEqual(entities[0]["confidence"], low_conf)


if __name__ == "__main__":
    unittest.main()
