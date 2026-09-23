import os
import re
import json
import difflib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from app.services.ocr import ocr_service


class FIRDatasetEvaluator:
    """
    Evaluates PaddleOCR performance on the ICDAR2023 FIR dataset.
    Compares ground-truth bounding box field annotations against OCR predictions.
    """

    DEFAULT_DATASET_DIR = Path.home() / "Downloads" / "FIR_Dataset_ICDAR2023-main"
    CATEGORY_MAP: Dict[int, str] = {
        0: "Police Station",
        1: "Year",
        2: "Statutes",
        3: "Complainant Name",
    }

    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = dataset_dir or self.DEFAULT_DATASET_DIR
        self.annotations_file = self.dataset_dir / "FIR_details.json"
        self.images_dir = self.dataset_dir / "FIR_images_v1"

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for comparison:
        - Lowercase
        - Trim whitespace & collapse repeated spaces
        - Remove non-alphanumeric punctuation
        """
        if not text:
            return ""
        text = text.lower()
        # Remove non-alphanumeric characters except spaces
        text = re.sub(r"[^\w\s]", "", text)
        # Collapse repeated whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def compute_box_overlap(boxA: List[float], boxB: List[float]) -> float:
        """
        Compute Intersection over Minimum Area for two bounding boxes [x1, y1, x2, y2].
        """
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter_width = max(0.0, xB - xA)
        inter_height = max(0.0, yB - yA)
        inter_area = inter_width * inter_height

        if inter_area <= 0.0:
            return 0.0

        boxA_area = max(0.0, boxA[2] - boxA[0]) * max(0.0, boxA[3] - boxA[1])
        boxB_area = max(0.0, boxB[2] - boxB[0]) * max(0.0, boxB[3] - boxB[1])

        min_area = min(boxA_area, boxB_area)
        if min_area <= 0.0:
            return 0.0

        return inter_area / min_area

    def load_annotations(self, json_path: Optional[Path] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load FIR_details.json and group annotations by image_name.
        """
        target_path = json_path or self.annotations_file
        if not target_path.exists():
            raise FileNotFoundError(f"Annotations file not found at: {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            raw_annotations = json.load(f)

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for ann in raw_annotations:
            if not isinstance(ann, dict):
                continue
            img_name = ann.get("image_name")
            if img_name:
                grouped.setdefault(img_name, []).append(ann)

        return grouped

    def evaluate(self, max_images: int = 10) -> Dict[str, Any]:
        """
        Run OCR evaluation over up to max_images from the dataset.

        Args:
            max_images: Maximum number of dataset images to evaluate.

        Returns:
            Dict containing overall metrics, per-field breakdowns, and unmatched examples.
        """
        if not self.dataset_dir.exists():
            raise FileNotFoundError(
                f"FIR Dataset directory not found at: {self.dataset_dir}. "
                "Ensure 'FIR_Dataset_ICDAR2023-main' is in your Downloads folder."
            )

        grouped_anns = self.load_annotations()
        target_image_names = list(grouped_anns.keys())[:max_images]

        total_annotations = 0
        total_exact = 0
        total_fuzzy = 0
        conf_scores: List[float] = []
        unmatched_examples: List[Dict[str, Any]] = []

        # Per field tracking
        per_field: Dict[str, Dict[str, Any]] = {
            field_name: {
                "total_annotations": 0,
                "exact_matches": 0,
                "fuzzy_matches": 0,
                "unmatched": 0,
                "exact_match_pct": 0.0,
                "fuzzy_match_pct": 0.0,
            }
            for field_name in self.CATEGORY_MAP.values()
        }

        images_evaluated = 0

        for img_name in target_image_names:
            img_path = self.images_dir / img_name
            if not img_path.exists():
                continue

            with open(img_path, "rb") as f:
                img_bytes = f.read()

            try:
                ocr_result = ocr_service.process_document(img_bytes, img_name)
            except Exception as e:
                print(f"Error OCR processing {img_name}: {e}")
                continue

            images_evaluated += 1
            ocr_regions = ocr_result.get("regions", [])
            image_anns = grouped_anns[img_name]

            for ann in image_anns:
                gt_bbox = ann.get("bbox", [0, 0, 0, 0])
                gt_text = ann.get("text", "")
                cat_id = ann.get("category_id", 0)
                cat_name = self.CATEGORY_MAP.get(cat_id, "Unknown")

                # Associate OCR predictions overlapping the GT bbox
                matched_ocr_texts = []
                matched_confs = []

                for reg in ocr_regions:
                    ocr_bbox = reg.get("bbox", [0, 0, 0, 0])
                    overlap = self.compute_box_overlap(gt_bbox, ocr_bbox)
                    if overlap >= 0.10:
                        matched_ocr_texts.append(reg.get("text", ""))
                        matched_confs.append(reg.get("confidence", 0.0))

                # Fallback: if no spatial overlap found, check substring matching
                if not matched_ocr_texts:
                    norm_gt_str = self.normalize_text(gt_text)
                    if norm_gt_str:
                        for reg in ocr_regions:
                            reg_text_norm = self.normalize_text(reg.get("text", ""))
                            if norm_gt_str in reg_text_norm or reg_text_norm in norm_gt_str:
                                matched_ocr_texts.append(reg.get("text", ""))
                                matched_confs.append(reg.get("confidence", 0.0))
                                break

                pred_text = " ".join(matched_ocr_texts).strip()
                avg_conf = sum(matched_confs) / len(matched_confs) if matched_confs else 0.0
                if avg_conf > 0:
                    conf_scores.append(avg_conf)

                # Text comparison
                norm_gt = self.normalize_text(gt_text)
                norm_pred = self.normalize_text(pred_text)

                is_exact = (norm_gt == norm_pred) and (len(norm_gt) > 0)

                similarity = difflib.SequenceMatcher(None, norm_gt, norm_pred).ratio() if norm_gt else 0.0
                is_fuzzy = is_exact or (similarity >= 0.65) or (len(norm_gt) >= 3 and norm_gt in norm_pred)

                # Update metrics
                total_annotations += 1
                if cat_name in per_field:
                    per_field[cat_name]["total_annotations"] += 1

                if is_exact:
                    total_exact += 1
                    total_fuzzy += 1
                    if cat_name in per_field:
                        per_field[cat_name]["exact_matches"] += 1
                        per_field[cat_name]["fuzzy_matches"] += 1
                elif is_fuzzy:
                    total_fuzzy += 1
                    if cat_name in per_field:
                        per_field[cat_name]["fuzzy_matches"] += 1
                else:
                    if cat_name in per_field:
                        per_field[cat_name]["unmatched"] += 1
                    if len(unmatched_examples) < 15:
                        unmatched_examples.append({
                            "image_name": img_name,
                            "field_category": cat_name,
                            "ground_truth_text": gt_text,
                            "predicted_text": pred_text,
                            "gt_bbox": gt_bbox,
                            "ocr_confidence": round(avg_conf, 4),
                        })

        # Calculate percentages
        for field_name, f_data in per_field.items():
            tot = f_data["total_annotations"]
            if tot > 0:
                f_data["exact_match_pct"] = round((f_data["exact_matches"] / tot) * 100, 2)
                f_data["fuzzy_match_pct"] = round((f_data["fuzzy_matches"] / tot) * 100, 2)

        avg_confidence = round(sum(conf_scores) / len(conf_scores), 4) if conf_scores else 0.0
        overall_exact_pct = round((total_exact / total_annotations) * 100, 2) if total_annotations > 0 else 0.0
        overall_fuzzy_pct = round((total_fuzzy / total_annotations) * 100, 2) if total_annotations > 0 else 0.0

        return {
            "images_evaluated": images_evaluated,
            "annotations_evaluated": total_annotations,
            "overall_exact_match": f"{total_exact}/{total_annotations} ({overall_exact_pct}%)",
            "overall_fuzzy_match": f"{total_fuzzy}/{total_annotations} ({overall_fuzzy_pct}%)",
            "average_confidence": avg_confidence,
            "per_field_results": per_field,
            "unmatched_examples": unmatched_examples,
        }


# Singleton instance
fir_evaluator = FIRDatasetEvaluator()
