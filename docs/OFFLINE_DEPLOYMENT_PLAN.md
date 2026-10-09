# Offline Deployment Plan

## Objective
Package the entire multimodal RAG application, dependencies, models, and databases into a portable SSD bundle capable of being installed and run in a strictly air-gapped environment.

## Target Hardware Assumptions
*To be confirmed by the user. Currently assuming:*
- OS: Windows or Linux (TBD, requiring different bundling strategies)
- Storage: High-capacity SSD for transfer
- CPU/GPU: TBD (GPU highly recommended for OCR/Embeddings)

## SSD Directory Layout
```text
offline_bundle/
├── runtime/                 # Python installer or portable runtime
├── python_packages/         # Wheelhouse containing all pip dependencies (.whl)
├── system_dependencies/     # MSVC redistributables, apt packages, etc.
├── models/
│   ├── ocr_layout/          # e.g., Surya/PaddleOCR weights
│   ├── embeddings_text/     # e.g., BGE model files
│   ├── embeddings_image/    # e.g., CLIP model files
│   ├── reranker/            # e.g., BGE-Reranker files
│   └── llm/                 # .gguf files for LM Studio
├── postgresql/              # PostgreSQL installer and pgvector binaries
├── application/             # Application source code
├── scripts/                 # Installation, startup, and validation scripts
├── licenses/                # Open source license inventory
└── manifests/               # SHA-256 checksums and version lockfiles
```

## Offline Dependency Management
- **Python:** Use `pip download` to create a complete wheelhouse for the specific target OS architecture. Use `pip install --no-index --find-links=...` during installation.
- **HuggingFace Models:** Download complete repositories using `huggingface-cli download`. Load using `local_files_only=True` in transformers.
- **NLTK/Spacy:** Pre-download any required language data packs.

## Installation Workflow
1. Connect SSD to air-gapped machine.
2. Run `verify_checksums.py` to ensure bundle integrity.
3. Install PostgreSQL and pgvector.
4. Install Python runtime.
5. Create virtual environment and install from wheelhouse.
6. Configure environment variables pointing to local model directories on the SSD (or copy to local disk).
7. Run application health checks (no internet).
