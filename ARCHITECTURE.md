# System Architecture
- **Language:** Python 3.10+
- **Core App:** FastAPI (provides scalable, live demo capability).
- **Batch Processing:** A CLI module that triggers the FastAPI logic sequentially for the dataset.
- **AI Backend:** NVIDIA NIM API (via `openai` python library compatible client).
- **Document Processing:** `pytesseract` for basic OCR, standard `json`/`csv` parsers, and regex for text.
- **Fail-safes:** Asynchronous processing with robust `tenacity` retries.
