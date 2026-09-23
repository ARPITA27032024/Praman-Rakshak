# Kybernetes - Digital Evidence & Document Management System

Kybernetes is a digital evidence management backend designed for handling legal and law enforcement documents (such as FIRs, chargesheets, police reports, and witness statements).

## Core Principles & Security Constraints

1. **Preservation of Original**: Original uploaded documents are **NEVER** modified by AI or any workflow step.
2. **Redaction Safety**: All PII (Personally Identifiable Information) redactions are performed on a **separate copy**. The original file remains untouched.
3. **Pretrained AI & Local Processing**: Uses strong pretrained models (**PaddleOCR**) for text and bounding box extraction. No external APIs or cloud AI services are called.
4. **Factual OCR Integrity**: OCR text is preserved without hallucinated AI corrections.

---

## High-Level Architecture & Pipeline Flow

```
Document Upload 
   │
   ├──► 1. File Validation (MIME type, size limits)
   │
   ├──► 2. Bounding-Box Aware OCR (PaddleOCR)                   <-- [IMPLEMENTED]
   │
   ├──► 3. FIR Key Information Extraction (KIE)                <-- [IMPLEMENTED]
   │
   ├──► 4. PII Detection (Names, Addresses, Phones, DOB, IDs)   <-- [IMPLEMENTED]
   │
   ├──► 5. Document Classification & Tagging (Explainable Rules) <-- [IMPLEMENTED]
   │
   ├──► 6. PII Redaction (Creates a redacted COPY for public/court viewing)
   │
   └──► 7. Embeddings & Semantic Search (Indexes text for vector search)
```

---

## PII Detection Component Overview

### What PII Detection Does
The PII Detector scans OCR regions and KIE context to locate sensitive Personally Identifiable Information:
- **`PERSON_NAME`**: Identified via KIE complainant context and printed name labels (`Father's Name`, `Husband's Name`).
- **`ADDRESS`**: Identified via address label prompts (`Address`, `Residence`, `Village`, `P.O.`) and spatial line proximity.
- **`PHONE_NUMBER`**: Conservative 10-digit Indian phone number regexes (rejecting dates, FIR numbers, and statutes).
- **`EMAIL`**: Conservative email format regex matching.
- **`DATE_OF_BIRTH`**: Extracted ONLY when DOB prompt context (`DOB`, `Date of Birth`) is present.
- **`ID_NUMBER`**: Extracted ONLY when ID prompt context (`Aadhaar`, `Voter ID`, `Passport`, `DL No`) is present.

### Metadata Schema
Every detected entity includes:
- `type`: Category (`PERSON_NAME`, `ADDRESS`, `PHONE_NUMBER`, `EMAIL`, `DATE_OF_BIRTH`, `ID_NUMBER`)
- `text`: Exact un-altered OCR text snippet
- `confidence`: Explainable confidence score
- `bbox`: Spatial bounding box `[x1, y1, x2, y2]`
- `page`: Page number (starting at 1)
- `source`: `"ocr"`
- `detection_method`: `"kie_context"`, `"label_context"`, `"regex"`, or `"spatial_context"`

---

## Project Folder Structure

```
Kybernetes/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entrypoint & router registration
│   ├── config.py                # Environment configuration using pydantic-settings
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py            # GET /health endpoint router
│   │   ├── ocr.py               # POST /ocr endpoint router
│   │   ├── classification.py    # POST /classify endpoint router
│   │   ├── evaluation.py        # POST /evaluate/fir-dataset endpoint router
│   │   ├── kie.py               # POST /extract/fir endpoint router
│   │   └── pii.py               # POST /detect/pii endpoint router
│   ├── core/
│   │   └── __init__.py          # Core utilities module
│   └── services/
│       ├── __init__.py
│       ├── document_processor.py # Upload ingestion & pipeline orchestrator
│       ├── ocr.py                # Bounding-box aware PaddleOCR service
│       ├── classification.py     # Document classification service
│       ├── fir_dataset_evaluator.py # ICDAR2023 dataset evaluator service
│       ├── fir_kie.py            # Hybrid FIR Key Information Extraction service
│       ├── pii_detector.py       # PII Detection service
│       ├── redaction.py          # Copy redaction service (preserves original)
│       └── search.py             # Vector embeddings & semantic search service
├── samples/                      # Sample documents for testing
│   ├── sample_fir.png           # Synthesized test FIR image
│   └── real_fir.jpg             # Real scanned FIR document
├── scripts/
│   ├── test_ocr_endpoint.py     # Test script for POST /ocr
│   ├── test_classification_with_real_fir.py # Test script for classification
│   ├── test_evaluation_10_images.py # Test script for dataset evaluator
│   ├── test_kie_endpoint.py     # Test script for POST /extract/fir
│   └── test_pii_endpoint.py     # Test script for POST /detect/pii
├── tests/
│   ├── test_classification.py   # Unit tests for classification
│   ├── test_fir_dataset_evaluator.py # Unit tests for dataset evaluator
│   ├── test_fir_kie.py          # Unit tests for KIE service
│   └── test_pii_detector.py     # Unit tests for PII detector service
├── storage/                      # Local file storage (ignored by git)
│   ├── originals/               # Vault for untouched original documents
│   └── redacted/                # Storage for redacted document copies
├── .env.example                 # Template for environment configuration
├── .gitignore                   # Git exclusion configuration
├── requirements.txt             # Python project dependencies
└── README.md                    # Project documentation
```

---

## Module Overview

| Module / File | Purpose | Status |
| :--- | :--- | :--- |
| `app/main.py` | Initializes FastAPI server, sets up storage folders, mounts API routes. | Active |
| `app/config.py` | Central configuration file for environment variables and storage paths. | Active |
| `app/api/health.py` | API endpoint (`GET /health`) for system health monitoring. | Active |
| `app/api/ocr.py` | API endpoint (`POST /ocr`) for document text & bounding box extraction. | Active |
| `app/api/classification.py` | API endpoint (`POST /classify`) for document classification and tagging. | Active |
| `app/api/evaluation.py` | API endpoint (`POST /evaluate/fir-dataset`) for dataset benchmarking. | Active |
| `app/api/kie.py` | API endpoint (`POST /extract/fir`) for FIR key information extraction. | Active |
| `app/api/pii.py` | API endpoint (`POST /detect/pii`) for PII entity detection. | Active |
| `app/services/ocr.py` | Runs PaddleOCR and PyMuPDF to extract text, confidence scores, and bboxes. | Active |
| `app/services/fir_kie.py` | Extracts Police Station, Year, Statutes, and Complainant Name via spatial anchors. | Active |
| `app/services/pii_detector.py` | Detects names, addresses, phones, emails, DOB, and IDs across OCR/KIE outputs. | Active |

---

## Local Setup & Testing

### 1. Run All Unit Tests
```bash
python -m unittest discover -s tests
```

### 2. Start the FastAPI Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Test PII Detection Endpoint (`POST /detect/pii`)

#### Using cURL:
```bash
curl -X POST "http://127.0.0.1:8000/detect/pii" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@samples/real_fir.jpg"
```

#### Using Python Test Script:
```bash
python scripts/test_pii_endpoint.py
```

#### Response JSON:
```json
{
  "success": true,
  "pii_entities": [
    {
      "type": "PERSON_NAME",
      "text": "Saesmita choth.",
      "confidence": 0.8099,
      "bbox": [88.0, 306.0, 261.0, 344.0],
      "page": 1,
      "source": "ocr",
      "detection_method": "kie_context"
    },
    {
      "type": "ADDRESS",
      "text": "1081, South Kodalia, P.O+P/S- Neco Banackporce",
      "confidence": 0.7397,
      "bbox": [0.0, 427.0, 535.0, 454.0],
      "page": 1,
      "source": "ocr",
      "detection_method": "spatial_context"
    }
  ]
}
```
