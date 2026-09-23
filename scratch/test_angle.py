import io
from PIL import Image
import numpy as np
from app.services.ocr import ocr_service

with open('samples/real_fir.jpg', 'rb') as f:
    img_bytes = f.read()

img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
img_np = np.array(img_pil)

pipeline = ocr_service._get_pipeline()
results = list(pipeline.predict(img_np))
res = results[0]

doc_prep = res.get("doc_preprocessor_res")
if doc_prep:
    angle = doc_prep.get("angle")
    rot_img = doc_prep.get("rot_img")
    out_img = doc_prep.get("output_img")
    print(f"angle: {angle}")
    if rot_img is not None:
        print(f"rot_img shape: {rot_img.shape}")
    if out_img is not None:
        print(f"output_img shape: {out_img.shape}")
