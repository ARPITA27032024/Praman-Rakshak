import io
import logging
from PIL import Image
from app.services.ocr import ocr_service
from app.services.fir_kie import fir_kie_service
from app.services.pii_detector import pii_detector_service
from app.services.redaction import redaction_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

with open('samples/real_fir.jpg', 'rb') as f:
    img_bytes = f.read()

img = Image.open(io.BytesIO(img_bytes))
print(f"PIL Image size: {img.size}")

# 1. OCR Step
ocr_res = ocr_service.process_document(img_bytes, 'real_fir.jpg')
print(f"Total OCR regions: {len(ocr_res['regions'])}")

# 2. KIE Step
kie_res = fir_kie_service.extract_fields(ocr_res['regions'])

# 3. PII Detection Step (with logging)
print("\n--- RUNNING PII DETECTION ---")
pii_res = pii_detector_service.detect_pii(ocr_res['regions'], kie_res)

# 4. Redaction Step (with debug overlay enabled)
print("\n--- RUNNING REDACTION & DEBUG OVERLAY ---")
red_res = redaction_service.redact_document(
    img_bytes, 'real_fir.jpg', pii_res, confidence_threshold=0.60, generate_debug_overlay=True, ocr_regions=ocr_res['regions']
)

print("\n--- SUMMARY ---")
print("Redacted image path:", red_res['redacted_filepath'])
print("Debug overlay path:", red_res['debug_overlay_path'])
print("Redaction count:", red_res['redaction_count'])
print("Redactions:", red_res['redactions'])
