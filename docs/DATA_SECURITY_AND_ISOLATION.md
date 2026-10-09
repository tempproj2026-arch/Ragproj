# Data Security and Isolation

## Core Principle
The development environment and the air-gapped production environment must be completely isolated. Real document data will never be present in the development environment.

## 1. Development vs. Production Boundary
- **Development:** Uses ONLY openly licensed substitute documents.
- **Production:** Uses the highly sensitive actual documents, entirely on an air-gapped machine.
- No vectors, databases, or image crops from the development environment will be deployed to production (except for explicitly verified empty schemas/indexes).

## 2. Document Replacement & Clean Reset
We will validate isolation by performing a Document Replacement Test during development:
1. Ingest Dataset A.
2. Purge Dataset A using a formalized reset script.
3. Ingest Dataset B.
4. Verify no data, vectors, or metadata from Dataset A bleed into Dataset B's retrieval results.

## 3. Network Isolation Verification
- All external dependencies (HuggingFace, pip, system updates) will be satisfied strictly via the offline SSD bundle.
- Application code will explicitly set flags preventing remote fallbacks (e.g., `local_files_only=True` in HuggingFace `transformers`).
- We will test the deployment on a development machine with the network adapter physically disabled to ensure no silent failures occur.

## 4. Local Storage Security
- All caches (e.g., `~/.cache/huggingface`) will be pointed to specific directories within the application deployment folder to prevent pollution and ensure portability.
- Extracted texts, databases, and logs will be treated as highly sensitive in production. Logging levels will be configurable and default to excluding raw text.
