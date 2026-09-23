import io
from PIL import Image, ImageOps
import numpy as np
from app.services.ocr import ocr_service

with open('samples/real_fir.jpg', 'rb') as f:
    img_bytes = f.read()

img_pil = Image.open(io.BytesIO(img_bytes))
print("PIL Original Size:", img_pil.size)
print("PIL EXIF:", img_pil.getexif().get(274)) # Orientation tag

img_rgb = img_pil.convert("RGB")
img_np = np.array(img_rgb)

pipeline = ocr_service._get_pipeline()
results = list(pipeline.predict(img_np))

for i, res in enumerate(results):
    print(f"\n--- Result {i} Keys ---")
    if isinstance(res, dict):
        for k, v in res.items():
            if isinstance(v, (list, tuple)):
                print(f"  {k}: list of len {len(v)}")
            elif isinstance(v, np.ndarray):
                print(f"  {k}: ndarray shape {v.shape}")
            else:
                print(f"  {k}: {type(v)} -> {str(v)[:100]}")
