# Canonical Data Schema

The canonical representation of extracted content uses a JSON schema designed to preserve document hierarchy and layout information.

## Schema Hierarchy

### 1. Document
```json
{
  "document_id": "sha256_hash",
  "filename": "technical_manual.pdf",
  "title": "Configurable Book Title",
  "total_pages": 450,
  "ingestion_timestamp": "2024-01-01T00:00:00Z"
}
```

### 2. Page
```json
{
  "page_id": "doc_id_page_12",
  "document_id": "sha256_hash",
  "page_index": 12,
  "printed_page_number": "10",
  "image_path": "/data/images/doc_id/page_12.png",
  "width": 800,
  "height": 1200
}
```

### 3. Element
```json
{
  "element_id": "doc_id_page_12_elem_3",
  "page_id": "doc_id_page_12",
  "element_type": "table|figure|math|paragraph|heading",
  "reading_order": 3,
  "bounding_box": [x1, y1, x2, y2],
  "text": "Extracted text content...",
  "structured_content": {
    "html": "<table>...</table>",
    "latex": "\\sum..."
  },
  "image_path": "/data/images/crops/doc_id_page_12_elem_3.png",
  "caption_element_id": "doc_id_page_12_elem_4",
  "confidence_score": 0.95
}
```

### 4. Chunk
```json
{
  "chunk_id": "chunk_001",
  "source_element_ids": ["doc_id_page_12_elem_3", "doc_id_page_12_elem_4"],
  "text": "Combined chunk text preserving headers and context...",
  "metadata": {
    "document_id": "...",
    "page_index": 12,
    "chapter": "Introduction"
  }
}
```

## Storage Strategy
- JSON records will be serialized and stored in PostgreSQL.
- Large image assets (page images, figure crops) remain on disk, with relative paths stored in the JSON records.
