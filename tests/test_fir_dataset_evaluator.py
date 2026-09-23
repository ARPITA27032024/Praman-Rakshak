import sys
import os
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.fir_dataset_evaluator import FIRDatasetEvaluator


class TestFIRDatasetEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = FIRDatasetEvaluator(dataset_dir=Path("/non/existent/path"))

    def test_text_normalization(self):
        # Test lowercase, whitespace collapse, punctuation removal
        raw = "  Police  Station : Airport  #07/17!  "
        normalized = FIRDatasetEvaluator.normalize_text(raw)
        self.assertEqual(normalized, "police station airport 0717")

    def test_category_mapping(self):
        self.assertEqual(FIRDatasetEvaluator.CATEGORY_MAP[0], "Police Station")
        self.assertEqual(FIRDatasetEvaluator.CATEGORY_MAP[1], "Year")
        self.assertEqual(FIRDatasetEvaluator.CATEGORY_MAP[2], "Statutes")
        self.assertEqual(FIRDatasetEvaluator.CATEGORY_MAP[3], "Complainant Name")

    def test_box_overlap_computation(self):
        box1 = [10.0, 10.0, 50.0, 50.0]  # Area 1600
        box2 = [30.0, 30.0, 60.0, 60.0]  # Intersection [30, 30, 50, 50] Area 400
        # Overlap = 400 / 900 = 0.4444...
        overlap = FIRDatasetEvaluator.compute_box_overlap(box1, box2)
        self.assertGreater(overlap, 0.40)
        self.assertLess(overlap, 0.50)

        # Disjoint boxes
        box3 = [100.0, 100.0, 150.0, 150.0]
        self.assertEqual(FIRDatasetEvaluator.compute_box_overlap(box1, box3), 0.0)

    def test_load_annotations_with_temp_file(self):
        sample_annotations = [
            {"image_id": 1, "bbox": [10, 10, 50, 50], "category_id": 0, "image_name": "test1.jpg", "text": "Airport PS"},
            {"image_id": 1, "bbox": [10, 60, 50, 90], "category_id": 1, "image_name": "test1.jpg", "text": "2021"},
            {"image_id": 2, "bbox": [20, 20, 70, 70], "category_id": 3, "image_name": "test2.jpg", "text": "John Doe"},
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "FIR_details.json"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(sample_annotations, f)

            grouped = self.evaluator.load_annotations(json_path=tmp_path)
            self.assertEqual(len(grouped), 2)
            self.assertIn("test1.jpg", grouped)
            self.assertIn("test2.jpg", grouped)
            self.assertEqual(len(grouped["test1.jpg"]), 2)
            self.assertEqual(grouped["test1.jpg"][0]["text"], "Airport PS")

    def test_invalid_or_missing_annotation_file(self):
        missing_path = Path("/tmp/non_existent_fir_annotations_file.json")
        with self.assertRaises(FileNotFoundError):
            self.evaluator.load_annotations(json_path=missing_path)

    def test_evaluate_missing_dataset_directory(self):
        fake_evaluator = FIRDatasetEvaluator(dataset_dir=Path("/invalid/dataset/path"))
        with self.assertRaises(FileNotFoundError):
            fake_evaluator.evaluate(max_images=5)


if __name__ == "__main__":
    unittest.main()
