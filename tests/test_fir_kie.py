import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.fir_kie import fir_kie_service, FIRKeyInformationExtractor


class TestFIRKeyInformationExtractor(unittest.TestCase):

    def test_printed_label_detection(self):
        self.assertTrue(FIRKeyInformationExtractor.is_printed_label("Police Station:"))
        self.assertTrue(FIRKeyInformationExtractor.is_printed_label("FIRST INFORMATION REPORT"))
        self.assertTrue(FIRKeyInformationExtractor.is_printed_label("Complaint / Informant"))
        self.assertTrue(FIRKeyInformationExtractor.is_printed_label("a) Name ..."))
        self.assertFalse(FIRKeyInformationExtractor.is_printed_label("Central Cyber Cell"))
        self.assertFalse(FIRKeyInformationExtractor.is_printed_label("Rajesh Sharma"))

    def test_date_without_4digit_year_rejected(self):
        # 29.08.16 must NOT be accepted as Year
        ocr_regions = [
            {"text": "ovcrtemecof offenee Date 29.08.16", "confidence": 0.78, "bbox": [10, 10, 200, 30], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertIsNone(fields["year"]["value"])
        self.assertEqual(fields["year"]["validation"], "not_found")

    def test_valid_4digit_year_accepted(self):
        # 2016 must be accepted as Year
        ocr_regions = [
            {"text": "FIR Year: 2016", "confidence": 0.95, "bbox": [10, 10, 100, 30], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertEqual(fields["year"]["value"], "2016")
        self.assertEqual(fields["year"]["validation"], "valid")

    def test_date_containing_2016_extracts_2016_only(self):
        # Date containing 29.08.2016 should extract 2016
        ocr_regions = [
            {"text": "Date of Offence 29.08.2016", "confidence": 0.92, "bbox": [10, 10, 150, 30], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertEqual(fields["year"]["value"], "2016")
        self.assertEqual(fields["year"]["validation"], "valid")

    def test_statute_format_341_354_354B(self):
        ocr_regions = [
            {"text": "Sections 341/354/354(B)", "confidence": 0.88, "bbox": [10, 10, 200, 30], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertIsNotNone(fields["statutes"]["value"])
        self.assertIn("341/354/354(B)", fields["statutes"]["value"])
        self.assertEqual(fields["statutes"]["validation"], "valid")

    def test_inline_field_extraction(self):
        ocr_regions = [
            {"text": "Police Station: Airport PS", "confidence": 0.96, "bbox": [10, 10, 150, 30], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertEqual(fields["police_station"]["value"], "Airport PS")
        self.assertEqual(fields["police_station"]["validation"], "valid")

    def test_spatial_nearby_region_association(self):
        ocr_regions = [
            {"text": "Complainant:", "confidence": 0.99, "bbox": [10, 100, 100, 120], "page": 1},
            {"text": "Rajesh Sharma", "confidence": 0.94, "bbox": [110, 101, 220, 121], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertEqual(fields["complainant_name"]["value"], "Rajesh Sharma")
        self.assertEqual(fields["complainant_name"]["validation"], "valid")

    def test_printed_labels_never_become_values(self):
        ocr_regions = [
            {"text": "Complainant:", "confidence": 0.99, "bbox": [10, 100, 100, 120], "page": 1},
            {"text": "a) Name ...", "confidence": 0.85, "bbox": [110, 101, 150, 121], "page": 1},
        ]
        fields = fir_kie_service.extract_fields(ocr_regions)
        # "a) Name ..." is a label prompt, must NOT be returned as complainant value
        self.assertNotEqual(fields["complainant_name"]["value"], "a) Name ...")

    def test_missing_fields_return_null_and_not_found(self):
        ocr_regions = []
        fields = fir_kie_service.extract_fields(ocr_regions)
        self.assertIsNone(fields["police_station"]["value"])
        self.assertEqual(fields["police_station"]["validation"], "not_found")
        self.assertIsNone(fields["year"]["value"])
        self.assertEqual(fields["year"]["validation"], "not_found")
        self.assertIsNone(fields["statutes"]["value"])
        self.assertEqual(fields["statutes"]["validation"], "not_found")
        self.assertIsNone(fields["complainant_name"]["value"])
        self.assertEqual(fields["complainant_name"]["validation"], "not_found")


if __name__ == "__main__":
    unittest.main()
