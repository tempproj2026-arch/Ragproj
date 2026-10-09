# Evaluation Plan

## Substitute Dataset
We will construct an evaluation dataset from public-domain or openly licensed technical materials (e.g., open-access textbooks, old technical manuals, arXiv papers) that contain:
- Complex mathematical formulas
- Multi-column layouts
- Detailed tables
- Diagrams and figures with captions

## Evaluation Metrics

### 1. Extraction Metrics
- **OCR Accuracy:** Character Error Rate (CER) and Word Error Rate (WER) on text blocks.
- **Layout/Reading Order Accuracy:** Human-annotated comparison of expected element sequence vs. predicted sequence.
- **Table Extraction:** Structural accuracy (precision/recall of cell adjacency and content).
- **Formula Extraction:** Exact match or similarity of generated LaTeX compared to ground truth.

### 2. Retrieval Metrics
- **Recall@K:** Percentage of queries where the relevant chunk is within the top K results.
- **Mean Reciprocal Rank (MRR):** How far down the list the first relevant result appears.
- **Multimodal Retrieval:** Accuracy of finding the correct figure/table based on text queries describing them.

### 3. End-to-End Metrics
- **Answer Correctness:** Is the generated answer factually correct based on the text?
- **Groundedness/Hallucination Rate:** Are all claims in the generated answer directly supported by the retrieved citations?

## Automated Testing
- Unit tests for schema validation, metadata extraction, and idempotent ingestion.
- Integration tests simulating the complete ingestion-to-retrieval pipeline.
- Specifically test offline model loading capabilities (`local_files_only=True`).
