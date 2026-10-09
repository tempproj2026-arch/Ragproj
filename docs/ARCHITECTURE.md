# System Architecture

## High-Level Architecture
The system follows a modular, pipelined architecture designed for offline multimodal retrieval-augmented generation.

### 1. Ingestion & Page Preservation
- Input: PDF (Scanned or Digital), Image files.
- Process: Compute SHA-256, assign IDs, extract page images.
- Output: Standardized raw page dataset.

### 2. Layout Parsing & OCR
- Tools (Candidates): Surya, Docling, PaddleOCR.
- Process: Detect layout elements (tables, headers, text blocks, figures, equations). Determine reading order.
- Output: Bounding boxes and element classifications.

### 3. Specialized Extractors
- **Text:** Tesseract or specialized local OCR for text blocks.
- **Tables:** Table Transformer or structurally-aware OCR to JSON/HTML.
- **Math/Formulas:** Nougat, Pix2Struct, or specialized local math OCR to LaTeX.
- **Figures:** Cropped bounding boxes preserved as separate image files.

### 4. Canonical Structuring
- Process: Convert all extracted elements into a canonical JSON representation preserving hierarchical relationships (Document -> Page -> Element).

### 5. Chunking
- Strategy: Structure-aware chunking. Retains parent-child relationships, avoids splitting tables/equations, groups figures with captions.

### 6. Embeddings
- **Text:** Local HuggingFace embeddings (e.g., `BAAI/bge-m3` or `nomic-embed-text`).
- **Images/Visual:** CLIP variants (e.g., `siglip`) for visual retrieval.

### 7. Storage & Indexing
- Database: PostgreSQL with `pgvector` extension.
- Storage: Relational metadata combined with vector indices. Image crops stored on disk with paths in DB.

### 8. Retrieval
- Strategy: Hybrid search (Dense vector + Sparse/BM25) over text chunks. Multimodal retrieval for figures/tables.
- Reranker: Local cross-encoder reranker (e.g., `bge-reranker-v2-m3`).

### 9. Generation & Integration
- LLM Provider: Local LLM served via LM Studio.
- Application Interface: Model Context Protocol (MCP) server connecting the local RAG tools to the LLM environment.

## Component Responsibilities & Data Flow
1. Raw Document -> [Ingestion Module] -> Page Images
2. Page Images -> [Layout & OCR Module] -> Extracted Elements
3. Extracted Elements -> [Canonical Structuring] -> JSON Records
4. JSON Records -> [Chunker] -> Chunks
5. Chunks -> [Embedding Module] -> Vectors
6. Vectors & JSON -> [Vector Store] -> Indexed DB
7. User Query -> [MCP Server / Retriever] -> Retrieved Chunks
8. Retrieved Chunks + Query -> [LM Studio] -> Final Answer
