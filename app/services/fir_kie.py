import re
from typing import Dict, List, Any, Optional


class FIRKeyInformationExtractor:
    """
    Extracts structured FIR key information (Police Station, Year, Statutes, Complainant Name)
    from PaddleOCR text regions and bounding box coordinates [x1, y1, x2, y2].
    Includes field validation, source tracking, and confidence status ('valid', 'uncertain', 'not_found').
    """

    FIELD_ANCHORS = {
        "police_station": [
            r"\bpolice\s+station\b",
            r"\bat\s+the\s+police\s+station\b",
            r"\bp\.?s\.?\b",
        ],
        "year": [
            r"\byear\b",
            r"\bdate\b",
            r"\b154\s*cr\.?\s*p\.?\s*c\b",
        ],
        "statutes": [
            r"\bsections?\b",
            r"\bacts?\s*&\s*sections?\b",
            r"\bother\s+acts\b",
            r"\bunder\s+section\b",
            r"\bipc\b",
        ],
        "complainant_name": [
            r"\bcomplainant\b",
            r"\binformant\b",
            r"\bcomplaint\s*/?\s*information\b",
            r"a\)\s*name",
        ],
    }

    ALL_LABEL_PATTERNS = [
        r"\bfirst\s+information\s+report\b",
        r"\bpolice\s+station\b",
        r"\bat\s+the\s+police\s+station\b",
        r"\bplace\s+of\s+occurrence\b",
        r"\bcomplaint\s*/?\s*information\b",
        r"\bcomplainant\b",
        r"\binformant\b",
        r"\bother\s+acts\s*&\s*sections\b",
        r"\bsections?\b",
        r"\bacts?\b",
        r"\bg\.?d\.?\s*no\b",
        r"\bdate\s*/?\s*year\s+of\s+birth\b",
        r"\bnationality\b",
        r"\baddress\b",
        r"\baction\s+taken\b",
        r"\bdistrict\b",
        r"a\)\s*name(?:\s*\.\.\.)?",
        r"b\)\s*father",
        r"c\)\s*date",
        r"d\)\s*nationality",
    ]

    @classmethod
    def is_printed_label(cls, text: str) -> bool:
        """Check if text is purely a printed form label header or prompt."""
        text_clean = text.strip()
        if not text_clean:
            return True
        for pat in cls.ALL_LABEL_PATTERNS:
            if re.search(rf"^{pat}[\s:\.\-]*$", text_clean, re.IGNORECASE):
                return True
            if re.search(pat, text_clean, re.IGNORECASE) and len(text_clean) < 30 and not re.search(r"\b(19\d{2}|20\d{2})\b", text_clean):
                return True
        return False

    def extract_fields(self, ocr_regions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Extract structured FIR fields with validation metadata.

        Returns:
            Dict mapping field names to field metadata dicts:
            {
                "value": "...",       # or None
                "confidence": 0.0,
                "bbox": [x1, y1, x2, y2],
                "source": "ocr",
                "validation": "valid" | "uncertain" | "not_found"
            }
        """
        empty_field = {
            "value": None,
            "confidence": 0.0,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "source": "ocr",
            "validation": "not_found",
        }

        if not ocr_regions:
            return {
                "police_station": dict(empty_field),
                "year": dict(empty_field),
                "statutes": dict(empty_field),
                "complainant_name": dict(empty_field),
            }

        extracted_results: Dict[str, Dict[str, Any]] = {}

        for field_key in ["police_station", "year", "statutes", "complainant_name"]:
            field_res = self._extract_single_field(field_key, ocr_regions)
            extracted_results[field_key] = field_res if field_res else dict(empty_field)

        return extracted_results

    def _extract_single_field(
        self, field_key: str, ocr_regions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Extract a single target field using inline, spatial, or regex matching."""

        # Priority Strategy for Year & Statutes: Specialized regex rules
        if field_key == "year":
            year_val = self._extract_year_by_regex(ocr_regions)
            if year_val:
                return year_val
            # If no 4-digit year found, do not fallback to arbitrary dates
            return None

        if field_key == "statutes":
            statute_val = self._extract_statutes_by_regex(ocr_regions)
            if statute_val:
                return statute_val

        # Strategy 2: Inline extraction
        inline_val = self._extract_inline_value(field_key, ocr_regions)
        if inline_val:
            return inline_val

        # Strategy 3: Spatial proximity matching
        spatial_val = self._extract_spatial_value(field_key, ocr_regions)
        if spatial_val:
            return spatial_val

        return None

    def _extract_year_by_regex(
        self, ocr_regions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Find 4-digit year (19xx or 20xx).
        Strict Rule: Must be a 4-digit year. Full dates such as '29.08.16' or '15/01/17' without a 4-digit year are rejected.
        If a full date contains a 4-digit year (e.g. '15/01/2017'), ONLY the 4-digit year '2017' is extracted.
        """
        year_candidates = []

        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            # Extract 4-digit year
            matches = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
            for yr in matches:
                score = round(float(reg.get("confidence", 0.0)), 4)
                bbox = reg.get("bbox", [0.0, 0.0, 0.0, 0.0])
                year_candidates.append((yr, score, bbox))

        if year_candidates:
            best_year, best_score, best_bbox = max(year_candidates, key=lambda x: x[1])
            validation = "valid" if best_score >= 0.70 else "uncertain"
            return {
                "value": best_year,
                "confidence": best_score,
                "bbox": best_bbox,
                "source": "ocr",
                "validation": validation,
            }

        return None

    def _extract_statutes_by_regex(
        self, ocr_regions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Locate statutory section numbers (e.g., 341/354/354(B), 341, 354, 354(B), IPC 341/354, Sections 341/354).
        Excludes unrelated form numbers like GD numbers or 5-digit form IDs.
        """
        statute_patterns = [
            r"\b341\s*[/,]\s*354\s*[/,]\s*354\s*\([AB\d]+\)",
            r"\b341\s*[/,]\s*354\s*[/,]\s*354\b",
            r"\b(?:ipc|sections?)\s*\d{3}\s*(?:[/\,]\s*\d{3})+\b",
            r"\b\d{3}\s*(?:[/\,]\s*\d{3})+(?:\s*\([A-Z0-9]+\))*\s*(?:IPC|Cr\.?P\.?C|P\.?S)?\b",
            r"\b\d{3}\s*\([A-Z0-9]+\)\s*(?:[/\,]\s*\d{3})*\b",
            r"\b\d{3}/[0-9/A-Z\(\)]+",
        ]

        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            # Ignore full dates like 15.01.2017
            if re.search(r"\b\d{2}/\d{2}/\d{2,4}\b", text):
                continue

            for pat in statute_patterns:
                match = re.search(pat, text, re.IGNORECASE)
                if match:
                    found_str = match.group(0).strip()
                    # Filter out isolated short numbers
                    if len(found_str) >= 3 and not re.match(r"^\d{1,4}$", found_str):
                        score = round(float(reg.get("confidence", 0.0)), 4)
                        validation = "valid" if score >= 0.70 else "uncertain"
                        return {
                            "value": found_str,
                            "confidence": score,
                            "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                            "source": "ocr",
                            "validation": validation,
                        }

        return None

    def _extract_inline_value(
        self, field_key: str, ocr_regions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Look for inline value inside the same OCR text line after a colon or prompt."""
        patterns = self.FIELD_ANCHORS[field_key]

        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            for pat in patterns:
                match = re.search(rf"({pat})[\s:\.\-]+\s*(.+)$", text, re.IGNORECASE)
                if match:
                    val_str = match.group(2).strip()
                    if val_str and not self.is_printed_label(val_str) and len(val_str) >= 2:
                        score = round(float(reg.get("confidence", 0.0)), 4)
                        validation = "valid" if score >= 0.70 else "uncertain"
                        return {
                            "value": val_str,
                            "confidence": score,
                            "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                            "source": "ocr",
                            "validation": validation,
                        }
        return None

    def _extract_spatial_value(
        self, field_key: str, ocr_regions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Search spatially for candidate value regions adjacent to a field label anchor."""
        anchor_patterns = self.FIELD_ANCHORS[field_key]

        anchor_reg = None
        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            for pat in anchor_patterns:
                if re.search(pat, text, re.IGNORECASE):
                    anchor_reg = reg
                    break
            if anchor_reg:
                break

        if not anchor_reg:
            return None

        abox = anchor_reg.get("bbox", [0, 0, 0, 0])
        ax1, ay1, ax2, ay2 = abox

        candidate_regions = []

        for reg in ocr_regions:
            if reg == anchor_reg:
                continue
            rtext = reg.get("text", "").strip()
            if not rtext or self.is_printed_label(rtext):
                continue

            rbox = reg.get("bbox", [0, 0, 0, 0])
            rx1, ry1, rx2, ry2 = rbox

            # Spatial condition A: To the right on same line (vertical overlap)
            vert_overlap = max(0.0, min(ay2, ry2) - max(ay1, ry1))
            if vert_overlap > 2.0 and rx1 >= ax1 - 10.0 and (rx1 - ax2) < 300.0:
                dist = abs(rx1 - ax2)
                candidate_regions.append((reg, dist, "right"))

            # Spatial condition B: Below label (horizontal overlap)
            horiz_overlap = max(0.0, min(ax2, rx2) - max(ax1, rx1))
            if horiz_overlap > 3.0 and ry1 >= ay1 and (ry1 - ay2) < 100.0:
                dist = abs(ry1 - ay2)
                candidate_regions.append((reg, dist, "below"))

        if candidate_regions:
            # Sort by spatial proximity distance
            candidate_regions.sort(key=lambda x: x[1])
            best_reg, _, _ = candidate_regions[0]
            val_text = best_reg.get("text", "").strip()

            if val_text and not self.is_printed_label(val_text):
                score = round(float(best_reg.get("confidence", 0.0)), 4)
                validation = "valid" if score >= 0.70 else "uncertain"
                return {
                    "value": val_text,
                    "confidence": score,
                    "bbox": best_reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                    "source": "ocr",
                    "validation": validation,
                }

        return None


# Singleton instance
fir_kie_service = FIRKeyInformationExtractor()
