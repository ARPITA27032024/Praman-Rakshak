import io
from PIL import Image
import numpy as np
from app.services.ocr import ocr_service

with open('samples/real_fir.jpg', 'rb') as f:
    img_bytes = f.read()

img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
img_np = np.array(img_pil)
print("Input img_np shape:", img_np.shape) # (1024, 642, 3)

pipeline = ocr_service._get_pipeline()
results = list(pipeline.predict(img_np))
res = results[0]

doc_prep = res.get("doc_preprocessor_res")
if doc_prep:
    print("DocPreprocessorResult attributes/dict:")
    if hasattr(doc_prep, "keys"):
        print("keys:", doc_prep.keys())
    if hasattr(doc_prep, "output_img"):
        out_img = doc_prep["output_img"] if isinstance(doc_prep, dict) else getattr(doc_prep, "output_img", None)
        if out_img is not None:
            print("doc_preprocessor output_img shape:", out_img.shape)
    if hasattr(doc_prep, "rotate_angle"):
        print("rotate_angle:", doc_prep.get("rotate_angle") if isinstance(doc_prep, dict) else getattr(doc_prep, "rotate_angle", None))
