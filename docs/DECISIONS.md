# Architecture Decisions

## 1. Database: PostgreSQL + pgvector
*Decision:* Use PostgreSQL with the `pgvector` extension instead of standalone vector databases (like Chroma or Milvus).
*Rationale:* PostgreSQL allows us to strongly link relational document metadata (the canonical JSON schema) with vectors, supporting complex metadata filtering and ensuring ACID compliance. It is easily portable to an offline environment via standard installers.

## 2. Ingestion/Parsing Framework
*Decision:* Deferred. Needs empirical testing in Milestone 3.
*Candidates:*
- **Surya:** Excellent open-source OCR and layout parsing, runs well locally.
- **Docling:** IBM's new framework, very strong at tables and reading order.
- **PaddleOCR:** Fast, robust, but sometimes struggles with complex nested tables.
*Next Steps:* Evaluate Docling and Surya on the substitute dataset.

## 3. Embedding Models
*Decision:* Use HuggingFace sentence-transformers natively loaded from disk.
*Candidates:* `BAAI/bge-m3` (supports multi-lingual and dense/sparse). `nomic-embed-text` (large context window).
*Visual:* `siglip` for image-to-text / image-to-image figure retrieval.

## 4. Language
*Decision:* Python (3.10+).
*Rationale:* De facto standard for AI/ML engineering, compatible with all required ML libraries.

## 5. Development Tooling
*Decision:* Use `uv` or `poetry` for dependency management.
*Rationale:* Standard `pip` lacks strict lockfiles by default. Reproducible lockfiles are absolutely essential for constructing the offline SSD bundle without version conflicts.

## 6. LLM Interface
*Decision:* Model Context Protocol (MCP) server wrapping the retriever, communicating with LM Studio.
*Rationale:* LM Studio provides a robust, easy-to-install local interface for serving LLMs (like Llama-3 8B or Mistral). MCP allows the LLM to seamlessly invoke our local retrieval functions.
