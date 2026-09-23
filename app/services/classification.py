import re
from typing import Dict, List, Any, Tuple


class DocumentClassifier:
    """
    Explainable, rule-based document classification and tagging service.
    Analyzes OCR text for strong printed headings, structural indicators, and keywords.
    """

    # Category definitions with weighted indicators and metadata tags
    CATEGORIES: Dict[str, Dict[str, Any]] = {
        "FIR": {
            "tags": ["police-record", "criminal-case", "fir", "first-information-report"],
            "indicators": [
                (r"\bfirst\s+information\s+report\b", "First Information Report", 0.45),
                (r"\bf\.?i\.?r\b", "FIR", 0.35),
                (r"\b154\s*(?:cr\.?\s*p\.?\s*c|code\s+of\s+criminal\s+procedure)?\b", "154 Cr.P.C.", 0.35),
                (r"\bpolice\s+station\b|\bp\.?s\.?\b", "Police Station", 0.20),
                (r"\bplace\s+of\s+occurrence\b", "Place of Occurrence", 0.20),
                (r"\bcomplaint\s*/?\s*information\b|\bcomplainant\b", "Complaint / Informant", 0.20),
                (r"\bg\.?d\.?\s*no\b", "G.D. No", 0.15),
                (r"\baction\s+taken\b", "Action Taken", 0.15),
                (r"\bj\.?p\.?\s*form\b|\bform\s+no\b", "Form No", 0.15),
                (r"\bother\s+acts\s*&\s*sections\b", "Other Acts & Sections", 0.15),
            ]
        },
        "Charge Sheet": {
            "tags": ["police-record", "criminal-case", "charge-sheet", "final-report"],
            "indicators": [
                (r"\bcharge\s*sheet\b|\bfinal\s+report\b", "Charge Sheet / Final Report", 0.45),
                (r"\b173\s*(?:cr\.?\s*p\.?\s*c)?\b", "173 Cr.P.C.", 0.35),
                (r"\baccused\s+(?:person|persons|name)?\b", "Accused Persons", 0.25),
                (r"\bmagistrate\b|\bcourt\b", "Magistrate / Court", 0.20),
                (r"\binvestigating\s+officer\b|\bi\.?o\.?\b", "Investigating Officer", 0.20),
                (r"\boffence[s]?\b|\bipc\b|\bpenal\s+code\b", "Offence / IPC", 0.15),
            ]
        },
        "Witness Statement": {
            "tags": ["legal-record", "witness-statement", "deposition", "investigation"],
            "indicators": [
                (r"\bwitness\s+statement\b|\bstatement\s+of\s+witness\b", "Witness Statement", 0.45),
                (r"\b161\s*(?:cr\.?\s*p\.?\s*c)?\b|\b164\s*(?:cr\.?\s*p\.?\s*c)?\b", "161/164 Cr.P.C.", 0.40),
                (r"\bstatement\s+recorded\b|\bdeposition\b", "Statement Recorded", 0.30),
                (r"\bwitness\s+name\b|\bdeponent\b", "Witness Name", 0.20),
                (r"\btestimony\b|\bsworn\b", "Testimony", 0.15),
            ]
        },
        "Police Report": {
            "tags": ["police-record", "police-report", "incident-report"],
            "indicators": [
                (r"\bpolice\s+report\b|\bincident\s+report\b", "Police Report", 0.45),
                (r"\bdaily\s+diary\b|\bgeneral\s+diary\b|\bgd\s+entry\b", "General / Daily Diary", 0.35),
                (r"\bcase\s+diary\b", "Case Diary", 0.30),
                (r"\binvestigating\s+officer\b|\bduty\s+officer\b", "Investigating / Duty Officer", 0.20),
            ]
        },
        "Medical Report": {
            "tags": ["medical-record", "medico-legal", "hospital-report"],
            "indicators": [
                (r"\bmedical\s+report\b|\bmedico\s*-\s*legal\b|\bmlc\b", "Medico-Legal / MLC", 0.45),
                (r"\bpost\s*mortem\b|\bautopsy\b", "Post Mortem / Autopsy", 0.45),
                (r"\bhospital\b|\bmedical\s+officer\b|\bdoctor\b", "Hospital / Doctor", 0.25),
                (r"\binjury\b|\binjuries\b|\bphysical\s+examination\b", "Injuries / Examination", 0.20),
                (r"\bcause\s+of\s+death\b", "Cause of Death", 0.20),
            ]
        },
        "Evidence/Forensic Report": {
            "tags": ["forensic-record", "evidence-report", "lab-analysis"],
            "indicators": [
                (r"\bforensic\s+(?:report|examination|science|laboratory)\b|\bfsl\b", "Forensic Report / FSL", 0.45),
                (r"\bevidence\s+analysis\b|\bballistics\b|\bchemical\s+analysis\b|\bdna\b", "Evidence Analysis", 0.40),
                (r"\bexhibits?\b|\bsealed\s+parcel\b", "Exhibits / Sealed Parcel", 0.25),
                (r"\blaboratory\s+reference\b", "Lab Reference", 0.20),
            ]
        }
    }

    CONFIDENCE_THRESHOLD = 0.30

    def classify_text(self, text: str) -> Dict[str, Any]:
        """
        Classify document text into standard categories based on explainable keyword & heading matching.

        Args:
            text: OCR-extracted document text

        Returns:
            Dict containing document_type, confidence score, matched_indicators, and tags.
        """
        if not text or not text.strip():
            return {
                "document_type": "Other",
                "confidence": 0.0,
                "tags": ["unclassified", "document"],
                "matched_indicators": [],
            }

        best_category: str = "Other"
        max_score: float = 0.0
        best_matched_indicators: List[str] = []
        best_tags: List[str] = ["unclassified", "document"]

        # Evaluate each candidate category
        for cat_name, cat_meta in self.CATEGORIES.items():
            category_score, matched_labels = self._evaluate_category(text, cat_meta["indicators"])

            if category_score > max_score:
                max_score = category_score
                best_category = cat_name
                best_matched_indicators = matched_labels
                best_tags = cat_meta["tags"]

        # If highest score does not meet the confidence threshold, fallback to "Other"
        if max_score < self.CONFIDENCE_THRESHOLD:
            return {
                "document_type": "Other",
                "confidence": round(max_score, 2),
                "tags": ["unclassified", "document"],
                "matched_indicators": best_matched_indicators,
            }

        return {
            "document_type": best_category,
            "confidence": min(round(max_score, 2), 1.0),
            "tags": best_tags,
            "matched_indicators": best_matched_indicators,
        }

    def _evaluate_category(self, text: str, indicators: List[Tuple[str, str, float]]) -> Tuple[float, List[str]]:
        """Evaluate matched indicators and calculate aggregate score for a category."""
        score = 0.0
        matched_labels = []

        for pattern, label, weight in indicators:
            if re.search(pattern, text, re.IGNORECASE):
                score += weight
                matched_labels.append(label)

        return score, matched_labels


# Singleton instance
classifier_service = DocumentClassifier()
