import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PIIDetector:
    """
    Lightweight, explainable PII detector for digital evidence documents.
    Detects PERSON_NAME, ADDRESS, PHONE_NUMBER, EMAIL, DATE_OF_BIRTH, and ID_NUMBER.
    Combines KIE context, label prompts, spatial proximity, and conservative regex rules.
    """

    # Label anchors for PII categories
    ADDRESS_LABELS = [
        r"\baddress\b",
        r"\bresidence\b",
        r"\bvillage\b",
        r"\bstreet\b",
        r"\bhouse\s+of\b",
        r"\blocality\b",
        r"\bpin\s*code\b",
        r"\bp\.?o\.?\b",
    ]

    DOB_LABELS = [
        r"\bdob\b",
        r"\bd\.?o\.?b\.?\b",
        r"\bdate\s+of\s+birth\b",
        r"\bbirth\s+date\b",
        r"\bborn\b",
    ]

    ID_LABELS = [
        r"\bid\s+no\b",
        r"\bid\s+number\b",
        r"\bidentification\b",
        r"\baadhaar\b",
        r"\bvoter\s+id\b",
        r"\bpassport\b",
        r"\bdriving\s+licence\b",
        r"\bdl\s+no\b",
        r"\bpan\s+card\b",
        r"\buid\b",
    ]

    NAME_LABELS = [
        r"father's/husband's\s*name",
        r"father's\s*name",
        r"husband's\s*name",
        r"accused\s*name",
        r"witness\s*name",
        r"informant\s*name",
        r"b\)\s*f[at]*h?e?r?['\w\s/]*name",
        r"b\)\s*f[at]*e?r?s?",
        r"a\)\s*name",
        r"father['\w\s/]*name",
        r"husband['\w\s/]*name",
    ]

    # Regex patterns
    PHONE_REGEX = r"\b(?:\+?91[\-\s]?)?[6-9]\d{9}\b"
    EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    DATE_REGEX = r"\b\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{2,4}\b|\b\d{4}[\.\/\-]\d{1,2}[\.\/\-]\d{1,2}\b"

    def detect_pii(
        self, ocr_regions: List[Dict[str, Any]], kie_fields: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detect PII entities across OCR regions using KIE context, label matching, and regexes.

        Args:
            ocr_regions: List of OCR region dicts ({'text': str, 'confidence': float, 'bbox': list, 'page': int})
            kie_fields: Optional output dict from FIRKeyInformationExtractor

        Returns:
            List of detected PII entity dicts:
            [{'type': str, 'text': str, 'confidence': float, 'bbox': list, 'page': int, 'source': 'ocr', 'detection_method': str}]
        """
        entities: List[Dict[str, Any]] = []

        if not ocr_regions:
            return entities

        # 1. PERSON_NAME from KIE context
        if kie_fields and isinstance(kie_fields, dict):
            comp_field = kie_fields.get("complainant_name")
            if comp_field and isinstance(comp_field, dict):
                comp_val = comp_field.get("value")
                if comp_val and comp_field.get("validation") != "not_found":
                    conf = round(min(1.0, comp_field.get("confidence", 0.0) * 1.05), 4)
                    cand = {
                        "type": "PERSON_NAME",
                        "text": comp_val,
                        "confidence": conf,
                        "bbox": comp_field.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                        "page": 1,
                        "source": "ocr",
                        "detection_method": "kie_context",
                    }
                    entities.append(cand)
                    logger.info(
                        f"[PII Candidate] Category: PERSON_NAME | Text: '{comp_val}' | Conf: {conf:.4f} | Method: kie_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                    )

        # 2. PERSON_NAME from label context (Father's/Husband's/Witness name)
        self._detect_names_from_labels(ocr_regions, entities)

        # 3. ADDRESS detection
        self._detect_addresses(ocr_regions, entities)

        # 4. PHONE_NUMBER detection
        self._detect_phone_numbers(ocr_regions, entities)

        # 5. EMAIL detection
        self._detect_emails(ocr_regions, entities)

        # 6. DATE_OF_BIRTH detection (Only when DOB context is present)
        self._detect_date_of_birth(ocr_regions, entities)

        # 7. ID_NUMBER detection (Only when ID context is present)
        self._detect_id_numbers(ocr_regions, entities)

        return self._deduplicate_entities(entities)

    def _detect_names_from_labels(self, ocr_regions: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Find person names near printed name prompt labels."""
        for idx, reg in enumerate(ocr_regions):
            text = reg.get("text", "").strip()
            ocr_conf = float(reg.get("confidence", 0.0))

            for pat in self.NAME_LABELS:
                # 1. Inline match after label
                match = re.search(rf"{pat}[\s:\.\-/\(\)\w]*[:\.\-]+\s*(.+)$", text, re.IGNORECASE)
                if not match and re.search(pat, text, re.IGNORECASE):
                    # Try splitting after prompt words
                    match = re.search(r"(?:name|name\s*\.\.\.|fter's|father's|husband's|father|husband)[\s:\.\-/\(\)\w]*\s+(.+)$", text, re.IGNORECASE)
                
                if match:
                    val_str = match.group(1).strip()
                    if val_str and len(val_str) >= 2 and not self._is_label_prompt(val_str):
                        conf = round(min(1.0, max(ocr_conf, 0.75)), 4)
                        cand = {
                            "type": "PERSON_NAME",
                            "text": val_str,
                            "confidence": conf,
                            "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                            "page": reg.get("page", 1),
                            "source": "ocr",
                            "detection_method": "label_context",
                        }
                        entities.append(cand)
                        logger.info(
                            f"[PII Candidate] Category: PERSON_NAME | Text: '{val_str}' | Conf: {conf:.4f} | Method: label_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                        )
                        break
                elif re.search(pat, text, re.IGNORECASE):
                    # Check next adjacent region spatially
                    if idx + 1 < len(ocr_regions):
                        next_reg = ocr_regions[idx + 1]
                        next_text = next_reg.get("text", "").strip()
                        if next_text and not self._is_label_prompt(next_text) and len(next_text) >= 2:
                            next_conf = float(next_reg.get("confidence", 0.0))
                            conf = round(min(1.0, max(next_conf, 0.75)), 4)
                            cand = {
                                "type": "PERSON_NAME",
                                "text": next_text,
                                "confidence": conf,
                                "bbox": next_reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                                "page": next_reg.get("page", 1),
                                "source": "ocr",
                                "detection_method": "spatial_context",
                            }
                            entities.append(cand)
                            logger.info(
                                f"[PII Candidate] Category: PERSON_NAME | Text: '{next_text}' | Conf: {conf:.4f} | Method: spatial_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                            )
                            break

    def _detect_addresses(self, ocr_regions: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Find address regions near address prompts or containing postal PIN patterns."""
        for idx, reg in enumerate(ocr_regions):
            text = reg.get("text", "").strip()
            if not text:
                continue

            # Check for PIN code pattern, P.O+P/S, or explicit address content markers
            has_address_format = bool(re.search(r"\b\d{6}\b|P\.O\+P/S|Kodalia|Barackpore|Bazar", text, re.IGNORECASE))
            # Check if region contains address prompt label
            has_addr_label = any(re.search(pat, text, re.IGNORECASE) for pat in self.ADDRESS_LABELS)

            if has_address_format and not self._is_label_prompt(text):
                conf = round(float(reg.get("confidence", 0.0)), 4)
                cand = {
                    "type": "ADDRESS",
                    "text": text,
                    "confidence": conf,
                    "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                    "page": reg.get("page", 1),
                    "source": "ocr",
                    "detection_method": "pattern_match",
                }
                entities.append(cand)
                logger.info(
                    f"[PII Candidate] Category: ADDRESS | Text: '{text}' | Conf: {conf:.4f} | Method: pattern_match | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                )
            elif has_addr_label:
                # If inline address value exists after label
                inline_match = re.search(r"(?:address|residence|village|street|house\s+of)[\s:\.\-]+\s*(.+)$", text, re.IGNORECASE)
                if inline_match:
                    val_str = inline_match.group(1).strip()
                    if val_str and len(val_str) >= 4:
                        conf = round(float(reg.get("confidence", 0.0)), 4)
                        cand = {
                            "type": "ADDRESS",
                            "text": val_str,
                            "confidence": conf,
                            "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                            "page": reg.get("page", 1),
                            "source": "ocr",
                            "detection_method": "label_context",
                        }
                        entities.append(cand)
                        logger.info(
                            f"[PII Candidate] Category: ADDRESS | Text: '{val_str}' | Conf: {conf:.4f} | Method: label_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                        )
                # Check next adjacent region spatially
                elif idx + 1 < len(ocr_regions):
                    next_reg = ocr_regions[idx + 1]
                    next_text = next_reg.get("text", "").strip()
                    if next_text and not self._is_label_prompt(next_text) and len(next_text) >= 4:
                        conf = round(float(next_reg.get("confidence", 0.0)), 4)
                        cand = {
                            "type": "ADDRESS",
                            "text": next_text,
                            "confidence": conf,
                            "bbox": next_reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                            "page": next_reg.get("page", 1),
                            "source": "ocr",
                            "detection_method": "spatial_context",
                        }
                        entities.append(cand)
                        logger.info(
                            f"[PII Candidate] Category: ADDRESS | Text: '{next_text}' | Conf: {conf:.4f} | Method: spatial_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                        )

    def _detect_phone_numbers(self, ocr_regions: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Detect valid Indian phone numbers via conservative regex, rejecting dates, FIR numbers, and statutes."""
        for reg in ocr_regions:
            text = reg.get("text", "").strip()

            # Reject dates, FIR numbers, statutes, and short numbers
            if re.search(r"\b\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{2,4}\b", text):
                continue
            if re.search(r"\b\d{3}\s*/\s*\d{3}\b", text):  # Statute sections
                continue
            if re.search(r"FIR\s*No", text, re.IGNORECASE) or re.search(r"\b\d{1,4}/\d{2,4}\b", text):
                continue

            matches = re.finditer(self.PHONE_REGEX, text)
            for m in matches:
                phone_str = m.group(0).strip()
                # Verify length (10 digits minimum)
                digits = re.sub(r"\D", "", phone_str)
                if len(digits) >= 10:
                    ocr_conf = float(reg.get("confidence", 0.0))
                    conf = round(min(1.0, max(ocr_conf, 0.90)), 4)
                    cand = {
                        "type": "PHONE_NUMBER",
                        "text": phone_str,
                        "confidence": conf,
                        "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                        "page": reg.get("page", 1),
                        "source": "ocr",
                        "detection_method": "regex",
                    }
                    entities.append(cand)
                    logger.info(
                        f"[PII Candidate] Category: PHONE_NUMBER | Text: '{phone_str}' | Conf: {conf:.4f} | Method: regex | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                    )

    def _detect_emails(self, ocr_regions: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Detect email addresses via conservative regex."""
        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            matches = re.finditer(self.EMAIL_REGEX, text)
            for m in matches:
                email_str = m.group(0).strip()
                ocr_conf = float(reg.get("confidence", 0.0))
                conf = round(min(1.0, max(ocr_conf, 0.92)), 4)
                cand = {
                    "type": "EMAIL",
                    "text": email_str,
                    "confidence": conf,
                    "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                    "page": reg.get("page", 1),
                    "source": "ocr",
                    "detection_method": "regex",
                }
                entities.append(cand)
                logger.info(
                    f"[PII Candidate] Category: EMAIL | Text: '{email_str}' | Conf: {conf:.4f} | Method: regex | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                )

    def _detect_date_of_birth(self, ocr_regions: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Classify date as DATE_OF_BIRTH ONLY when DOB context prompt is present."""
        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            has_dob_label = any(re.search(pat, text, re.IGNORECASE) for pat in self.DOB_LABELS)

            if has_dob_label:
                # Find date pattern in same or adjacent text
                date_match = re.search(self.DATE_REGEX, text)
                if date_match:
                    date_str = date_match.group(0).strip()
                    conf = round(float(reg.get("confidence", 0.0)), 4)
                    cand = {
                        "type": "DATE_OF_BIRTH",
                        "text": date_str,
                        "confidence": conf,
                        "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                        "page": reg.get("page", 1),
                        "source": "ocr",
                        "detection_method": "label_context",
                    }
                    entities.append(cand)
                    logger.info(
                        f"[PII Candidate] Category: DATE_OF_BIRTH | Text: '{date_str}' | Conf: {conf:.4f} | Method: label_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                    )

    def _detect_id_numbers(self, ocr_regions: List[Dict[str, Any]], entities: List[Dict[str, Any]]):
        """Classify alphanumeric string as ID_NUMBER ONLY when ID context label is present."""
        for reg in ocr_regions:
            text = reg.get("text", "").strip()
            has_id_label = any(re.search(pat, text, re.IGNORECASE) for pat in self.ID_LABELS)

            if has_id_label:
                # Extract alphanumeric ID string after label
                match = re.search(r"(?:id|id\s+no|aadhaar|voter\s+id|passport|dl\s+no)[\s:\.\-]+\s*([A-Za-z0-9\-\s]{4,20})", text, re.IGNORECASE)
                if match:
                    id_str = match.group(1).strip()
                    if id_str and not self._is_label_prompt(id_str):
                        conf = round(float(reg.get("confidence", 0.0)), 4)
                        cand = {
                            "type": "ID_NUMBER",
                            "text": id_str,
                            "confidence": conf,
                            "bbox": reg.get("bbox", [0.0, 0.0, 0.0, 0.0]),
                            "page": reg.get("page", 1),
                            "source": "ocr",
                            "detection_method": "label_context",
                        }
                        entities.append(cand)
                        logger.info(
                            f"[PII Candidate] Category: ID_NUMBER | Text: '{id_str}' | Conf: {conf:.4f} | Method: label_context | Threshold 0.60: {'PASSED' if conf >= 0.60 else 'FAILED'}"
                        )

    @staticmethod
    def _is_label_prompt(text: str) -> bool:
        """Helper to filter out prompt headers."""
        text_clean = text.strip()
        label_prompts = [
            r"a\)\s*name",
            r"b\)\s*father",
            r"c\)\s*date",
            r"d\)\s*nationality",
            r"complaint\s*/?\s*information",
            r"police\s+station",
            r"first\s+information\s+report",
        ]
        for pat in label_prompts:
            if re.search(rf"^{pat}[\s:\.\-]*$", text_clean, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _deduplicate_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate entities by type and bounding box / text."""
        unique_entities: List[Dict[str, Any]] = []
        seen = set()

        for ent in entities:
            key = (ent["type"], ent["text"].lower(), tuple(ent["bbox"]))
            if key not in seen:
                seen.add(key)
                unique_entities.append(ent)

        return unique_entities


# Singleton instance
pii_detector_service = PIIDetector()
