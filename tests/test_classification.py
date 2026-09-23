import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.classification import classifier_service


class TestDocumentClassification(unittest.TestCase):

    def test_fir_classification(self):
        text = "FIRST INFORMATION REPORT under section 154 Cr.P.C. at Police Station Airport. FIR No: 07/17"
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "FIR")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("fir", res["tags"])
        self.assertIn("First Information Report", res["matched_indicators"])

    def test_charge_sheet_classification(self):
        text = "FINAL REPORT / CHARGE SHEET under section 173 Cr.P.C. Accused Persons: John Doe. Court of Judicial Magistrate."
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "Charge Sheet")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("charge-sheet", res["tags"])
        self.assertIn("Charge Sheet / Final Report", res["matched_indicators"])

    def test_witness_statement_classification(self):
        text = "Statement of Witness recorded under Section 161 Cr.P.C. Witness Name: Ramesh Kumar. Deposition given on oath."
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "Witness Statement")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("witness-statement", res["tags"])

    def test_police_report_classification(self):
        text = "Police Report and General Diary GD Entry No 542. Case Diary submitted by Duty Officer at Police Station."
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "Police Report")
        self.assertGreaterEqual(res["confidence"], 0.50)
        self.assertIn("police-report", res["tags"])

    def test_medical_report_classification(self):
        text = "Medico-Legal Certificate MLC No 44. Post Mortem examination conducted by Medical Officer at City Hospital."
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "Medical Report")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("medico-legal", res["tags"])

    def test_forensic_report_classification(self):
        text = "Forensic Science Laboratory FSL Report. Chemical Analysis of Exhibits and Ballistics Evidence Analysis."
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "Evidence/Forensic Report")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertIn("forensic-record", res["tags"])

    def test_other_classification(self):
        text = "Random general text without any legal or police terminology."
        res = classifier_service.classify_text(text)
        self.assertEqual(res["document_type"], "Other")
        self.assertLess(res["confidence"], 0.30)
        self.assertIn("unclassified", res["tags"])


if __name__ == "__main__":
    unittest.main()
