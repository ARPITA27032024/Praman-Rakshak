"""
PII (Personally Identifiable Information) Detection Module.
Will detect names, phone numbers, email addresses, addresses, and sensitive identifiers.
"""


class PIIDetector:
    """
    Interface for identifying sensitive PII entities in extracted text and bounding boxes.
    """

    def detect_pii(self, text: str):
        """
        Scan text and return detected PII entities with entity types and span locations.
        """
        raise NotImplementedError("PII detection will be implemented in a subsequent phase.")
