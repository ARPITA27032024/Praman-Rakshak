import io
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageOps
import pymupdf
from app.config import settings

logger = logging.getLogger(__name__)


class RedactionService:
    """
    Redaction Service that creates a separate redacted COPY of a document or image.
    The original uploaded document is NEVER altered.
    Draws opaque black rectangles over PII bounding boxes with configurable padding and threshold filtering.
    """

    SUPPORTED_PII_TYPES = {
        "PERSON_NAME",
        "ADDRESS",
        "PHONE_NUMBER",
        "EMAIL",
        "DATE_OF_BIRTH",
        "ID_NUMBER",
    }

    def redact_document(
        self,
        file_bytes: bytes,
        filename: str,
        pii_entities: List[Dict[str, Any]],
        confidence_threshold: float = 0.60,
        padding: int = 4,
        generate_debug_overlay: bool = False,
        ocr_regions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Create a redacted COPY of the document with black rectangles over valid PII bounding boxes.

        Args:
            file_bytes: Original file binary bytes (never written to or overwritten)
            filename: Original file name
            pii_entities: List of PII entities detected by PIIDetector
            confidence_threshold: Minimum confidence score required to apply redaction (default 0.60)
            padding: Padding pixels added around bounding box boundaries (default 4px)
            generate_debug_overlay: If True, draws ALL OCR-detected boxes in red on a separate debug file
            ocr_regions: Optional OCR regions list required if generate_debug_overlay is True

        Returns:
            Dict containing:
            - redacted_filepath: Path to created redacted file
            - redacted_filename: Name of created redacted file
            - redaction_count: Number of redacted regions
            - redactions: Metadata list (EXCLUDES original sensitive text)
            - debug_overlay_path: Optional path to created debug overlay image
        """
        # Ensure redacted storage directory exists
        os.makedirs(settings.REDACTED_DIR, exist_ok=True)

        # 1. Filter valid PII entities matching criteria
        valid_entities, redaction_metadata = self._filter_entities(
            pii_entities, confidence_threshold
        )

        stem = Path(filename).stem
        ext = Path(filename).suffix.lower()

        if ext == ".pdf":
            output_filename = f"redacted_{stem}.pdf"
            output_filepath = str(Path(settings.REDACTED_DIR) / output_filename)
            self._redact_pdf(file_bytes, valid_entities, output_filepath, padding)
        else:
            output_filename = f"redacted_{stem}.png"
            output_filepath = str(Path(settings.REDACTED_DIR) / output_filename)
            self._redact_image(file_bytes, valid_entities, output_filepath, padding)

        debug_overlay_path = None
        if generate_debug_overlay and ocr_regions:
            debug_overlay_path = self.generate_debug_ocr_overlay(file_bytes, filename, ocr_regions)

        return {
            "redacted_filepath": output_filepath,
            "redacted_filename": output_filename,
            "redaction_count": len(valid_entities),
            "redactions": redaction_metadata,
            "debug_overlay_path": debug_overlay_path,
        }

    def generate_debug_ocr_overlay(
        self, file_bytes: bytes, filename: str, ocr_regions: List[Dict[str, Any]], padding: int = 0
    ) -> str:
        """
        Draw ALL OCR-detected bounding boxes (not just PII) in red outline (no fill)
        onto the original image/PDF and save to storage/redacted/debug_ocr_{stem}.png.
        """
        os.makedirs(settings.REDACTED_DIR, exist_ok=True)
        stem = Path(filename).stem
        ext = Path(filename).suffix.lower()
        output_filename = f"debug_ocr_{stem}.png"
        output_filepath = str(Path(settings.REDACTED_DIR) / output_filename)

        if ext == ".pdf":
            try:
                pdf_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
                if len(pdf_doc) > 0:
                    page = pdf_doc[0]
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    draw = ImageDraw.Draw(img)
                    w, h = img.size
                    for reg in ocr_regions:
                        bbox = reg.get("bbox")
                        if bbox and len(bbox) == 4:
                            x1, y1, x2, y2 = bbox
                            px1, py1, px2, py2 = self.pad_and_clamp_bbox([x1, y1, x2, y2], w, h, padding=padding)
                            draw.rectangle([px1, py1, px2, py2], outline=(255, 0, 0), width=2)
                    img.save(output_filepath, format="PNG")
                pdf_doc.close()
            except Exception as e:
                logger.error(f"Error creating PDF debug overlay: {e}")
        else:
            try:
                image = Image.open(io.BytesIO(file_bytes))
                image = ImageOps.exif_transpose(image).convert("RGB")
                draw = ImageDraw.Draw(image)
                w, h = image.size
                for reg in ocr_regions:
                    bbox = reg.get("bbox")
                    if bbox and len(bbox) == 4:
                        x1, y1, x2, y2 = bbox
                        px1, py1, px2, py2 = self.pad_and_clamp_bbox([x1, y1, x2, y2], w, h, padding=padding)
                        draw.rectangle([px1, py1, px2, py2], outline=(255, 0, 0), width=2)
                image.save(output_filepath, format="PNG")
            except Exception as e:
                logger.error(f"Error creating image debug overlay: {e}")

        return output_filepath

    def _filter_entities(
        self, pii_entities: List[Dict[str, Any]], confidence_threshold: float
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Filter PII entities by supported type, confidence threshold, and valid bounding box."""
        valid_entities = []
        redaction_metadata = []

        for ent in pii_entities:
            etype = ent.get("type")
            conf = float(ent.get("confidence", 0.0))
            bbox = ent.get("bbox")
            page = int(ent.get("page", 1))

            if etype not in self.SUPPORTED_PII_TYPES:
                logger.debug(f"[Redaction Filter] Rejected unsupported type '{etype}'")
                continue
            if conf < confidence_threshold:
                logger.info(
                    f"[Redaction Filter] Rejected {etype} candidate (conf: {conf:.4f} < threshold: {confidence_threshold:.2f})"
                )
                continue
            if not bbox or not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            if x2 <= x1 or y2 <= y1:
                continue

            valid_entities.append(ent)
            logger.info(
                f"[Redaction Filter] PASSED -> Redacting {etype} (conf: {conf:.4f} >= threshold: {confidence_threshold:.2f}) at bbox={bbox}"
            )

            # Metadata MUST NOT contain original sensitive text
            redaction_metadata.append({
                "type": etype,
                "bbox": [round(float(x), 2) for x in bbox],
                "page": page,
                "confidence": round(conf, 4),
            })

        return valid_entities, redaction_metadata

    def _redact_image(
        self, file_bytes: bytes, entities: List[Dict[str, Any]], output_filepath: str, padding: int
    ):
        """Process image document and draw black rectangles over PII bounding boxes."""
        try:
            image = Image.open(io.BytesIO(file_bytes))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except Exception as e:
            raise ValueError(f"Invalid image file for redaction: {str(e)}")

        draw = ImageDraw.Draw(image)
        w, h = image.size

        for ent in entities:
            x1, y1, x2, y2 = ent["bbox"]
            px1, py1, px2, py2 = self.pad_and_clamp_bbox([x1, y1, x2, y2], w, h, padding)
            # Draw opaque black rectangle
            draw.rectangle([px1, py1, px2, py2], fill=(0, 0, 0))

        # Save as PNG to avoid JPEG compression artifacts around black redaction rectangles
        image.save(output_filepath, format="PNG")

    def _redact_pdf(
        self, file_bytes: bytes, entities: List[Dict[str, Any]], output_filepath: str, padding: int
    ):
        """Process multi-page PDF document by rendering pages, applying redactions, and rebuilding PDF."""
        try:
            pdf_doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise ValueError(f"Invalid PDF file for redaction: {str(e)}")

        redacted_images: List[Image.Image] = []

        try:
            for page_idx, page in enumerate(pdf_doc, start=1):
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                w, h = img.size
                draw = ImageDraw.Draw(img)

                # Filter entities for current page
                page_entities = [e for e in entities if int(e.get("page", 1)) == page_idx]
                for ent in page_entities:
                    x1, y1, x2, y2 = ent["bbox"]
                    px1, py1, px2, py2 = self.pad_and_clamp_bbox([x1, y1, x2, y2], w, h, padding)
                    draw.rectangle([px1, py1, px2, py2], fill=(0, 0, 0))

                redacted_images.append(img)

            if redacted_images:
                # Save as new multi-page PDF
                redacted_images[0].save(
                    output_filepath,
                    format="PDF",
                    save_all=True,
                    append_images=redacted_images[1:],
                )
        finally:
            pdf_doc.close()

    @staticmethod
    def pad_and_clamp_bbox(
        bbox: List[float], image_width: int, image_height: int, padding: int = 4
    ) -> Tuple[int, int, int, int]:
        """Apply padding to bbox coordinates and clamp within image boundaries."""
        x1, y1, x2, y2 = bbox

        px1 = max(0, int(round(x1)) - padding)
        py1 = max(0, int(round(y1)) - padding)
        px2 = min(image_width, int(round(x2)) + padding)
        py2 = min(image_height, int(round(y2)) + padding)

        return px1, py1, px2, py2


# Singleton instance
redaction_service = RedactionService()
