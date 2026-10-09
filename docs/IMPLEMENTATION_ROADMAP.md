# Implementation Roadmap

This roadmap organizes the development into discrete milestones. We will proceed incrementally, requiring review before advancing.

## Milestone 1: Repository Assessment & Architecture (Current)
- **Deliverables:** Planning documents (`docs/`), repository inspection.
- **Status:** In Progress.

## Milestone 2: Substitute Dataset & Baseline
- **Deliverables:** Selection of 3-5 representative public-domain/open-licensed technical books. Establishment of ground-truth evaluation subsets.

## Milestone 3: Layout Parsing & Specialized Extraction
- **Deliverables:** Pipeline for text, tables, formulas, and figure extraction. Evaluation of candidate tools (Surya, Docling, etc.) against the substitute dataset.

## Milestone 4: Canonical Structured Representation
- **Deliverables:** JSON schema definition for Document, Page, and Element levels. Serializer and validator.

## Milestone 5: Structure-Aware Chunking
- **Deliverables:** Chunking logic that respects document hierarchy (e.g., keeps tables intact, links figures to captions).

## Milestone 6: Text and Image Embeddings
- **Deliverables:** Integration of local text and multimodal embedding models (e.g., BGE, SigLIP). Scripts for offline model loading.

## Milestone 7: Database & Indexing
- **Deliverables:** PostgreSQL + pgvector schema setup. Data loading and indexing logic. Collection isolation validation.

## Milestone 8: Retrieval & Evidence Evaluation
- **Deliverables:** Hybrid retrieval implementation, cross-encoder reranking, and source attribution logic. Evaluation against metrics (Recall@K).

## Milestone 9: MCP & LM Studio Integration
- **Deliverables:** MCP Server wrapping the retrieval tools. End-to-end testing with LM Studio.

## Milestone 10: Offline Bundle Preparation
- **Deliverables:** Scripts to package Python wheels, model weights, Postgres binaries, and deployment manifests onto an SSD.

## Milestone 11: Clean-Room Deployment Simulation
- **Deliverables:** Successful installation and end-to-end test in a network-disabled test environment.

## Milestone 12: Production Deployment Procedure
- **Deliverables:** Comprehensive installation manual and operational guide for the actual air-gapped environment.
