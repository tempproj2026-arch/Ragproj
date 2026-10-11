import time
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel

from .config import settings
from .logging import get_logger
from .db.connection import Database
from .embeddings import embed_texts, embed_figures
from .reranker import rerank_documents

logger = get_logger("ragcore.retriever")

class SearchResult(BaseModel):
    chunk_id: int
    document_slug: str
    page_number: int
    content_type: str
    content: str
    search_text: str
    section: Optional[str] = None
    score: float
    rank: int
    figure_image_path: Optional[str] = None

class FigureResult(BaseModel):
    figure_id: int
    document_slug: str
    page_number: int
    caption: Optional[str] = None
    description: Optional[str] = None
    image_path: str
    score: float

class HybridRetriever:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    def search_dense(
        self,
        query: str,
        limit: int = 20,
        content_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Performs semantic vector search using BGE-M3 1024-dim embeddings."""
        query_vec = embed_texts([query])[0]
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        c.id, c.document_id, d.slug AS doc_slug, c.page_number,
                        c.content_type, c.content, c.search_text, c.section,
                        1 - (c.embedding <=> %s::vector) AS dense_sim
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE (%s::text[] IS NULL OR c.content_type = ANY(%s::text[]))
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s;
                """, (query_vec, content_types, content_types, query_vec, limit))
                
                rows = cur.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "id": r[0],
                        "document_id": r[1],
                        "doc_slug": r[2],
                        "page_number": r[3],
                        "content_type": r[4],
                        "content": r[5],
                        "search_text": r[6],
                        "section": r[7],
                        "dense_score": float(r[8])
                    })
                return results

    def search_sparse(
        self,
        query: str,
        limit: int = 20,
        content_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Performs lexical BM25/FTS search using tsvector with websearch query syntax."""
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                # Use websearch_to_tsquery for natural English query parsing
                cur.execute("""
                    SELECT 
                        c.id, c.document_id, d.slug AS doc_slug, c.page_number,
                        c.content_type, c.content, c.search_text, c.section,
                        ts_rank_cd(c.tsv, websearch_to_tsquery('english', %s)) AS sparse_rank
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE c.tsv @@ websearch_to_tsquery('english', %s)
                      AND (%s::text[] IS NULL OR c.content_type = ANY(%s::text[]))
                    ORDER BY sparse_rank DESC
                    LIMIT %s;
                """, (query, query, content_types, content_types, limit))
                
                rows = cur.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "id": r[0],
                        "document_id": r[1],
                        "doc_slug": r[2],
                        "page_number": r[3],
                        "content_type": r[4],
                        "content": r[5],
                        "search_text": r[6],
                        "section": r[7],
                        "sparse_score": float(r[8])
                    })
                return results

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        content_types: Optional[List[str]] = None,
        candidate_pool_size: int = 20,
        use_reranker: bool = True
    ) -> List[SearchResult]:
        """
        Executes complete hybrid retrieval:
        1. Dense semantic search.
        2. Sparse BM25 / full-text search.
        3. Reciprocal Rank Fusion (RRF).
        4. Cross-Encoder reranking (or RRF score if reranker unavailable).
        """
        dense_results = self.search_dense(query, limit=candidate_pool_size, content_types=content_types)
        sparse_results = self.search_sparse(query, limit=candidate_pool_size, content_types=content_types)

        # Build candidate map and calculate RRF scores
        candidates: Dict[int, Dict[str, Any]] = {}
        rrf_scores: Dict[int, float] = {}

        # Dense ranking contribution
        for rank, item in enumerate(dense_results, start=1):
            c_id = item["id"]
            candidates[c_id] = item
            rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (self.rrf_k + rank))

        # Sparse ranking contribution
        for rank, item in enumerate(sparse_results, start=1):
            c_id = item["id"]
            if c_id not in candidates:
                candidates[c_id] = item
            rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (self.rrf_k + rank))

        if not candidates:
            return []

        # Sort candidates by combined RRF score
        sorted_candidate_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
        top_candidates = [candidates[cid] for cid in sorted_candidate_ids[:candidate_pool_size]]

        # Cross-Encoder reranking
        final_scores: List[float] = []
        final_ordered_candidates: List[Dict[str, Any]] = []

        if use_reranker and len(top_candidates) > 1:
            doc_texts = [c["search_text"] for c in top_candidates]
            rerank_results = rerank_documents(query, doc_texts, top_k=top_k)
            for orig_idx, score in rerank_results:
                final_ordered_candidates.append(top_candidates[orig_idx])
                final_scores.append(score)
        else:
            final_ordered_candidates = top_candidates[:top_k]
            final_scores = [rrf_scores[c["id"]] for c in final_ordered_candidates]

        # Fetch figure image paths for figure/table chunks
        results: List[SearchResult] = []
        for rank, (cand, score) in enumerate(zip(final_ordered_candidates[:top_k], final_scores[:top_k]), start=1):
            # Extract image path if this chunk is a figure
            fig_path = None
            if cand["content_type"] == "figure" and "![" in cand["content"]:
                # Parse markdown image syntax ![caption](path)
                import re
                m = re.search(r'!\[.*?\]\((.*?)\)', cand["content"])
                if m:
                    fig_path = m.group(1)

            results.append(SearchResult(
                chunk_id=cand["id"],
                document_slug=cand["doc_slug"],
                page_number=cand["page_number"],
                content_type=cand["content_type"],
                content=cand["content"],
                search_text=cand["search_text"],
                section=cand.get("section"),
                score=round(score, 4),
                rank=rank,
                figure_image_path=fig_path
            ))

        return results

    def search_figures(self, query: str, top_k: int = 3) -> List[FigureResult]:
        """
        Finds figures by semantic match on figure descriptions and captions.
        """
        # Query figure chunks through dense vector search
        figure_chunks = self.search_dense(query, limit=top_k * 2, content_types=["figure"])
        if not figure_chunks:
            return []

        # Map to figure table rows
        with Database.get_connection() as conn:
            with conn.cursor() as cur:
                results: List[FigureResult] = []
                for chunk in figure_chunks[:top_k]:
                    p_num = chunk["page_number"]
                    doc_slug = chunk["doc_slug"]
                    cur.execute("""
                        SELECT f.id, f.caption, f.description, f.image_path
                        FROM figures f
                        JOIN regions r ON f.region_id = r.id
                        JOIN pages p ON r.page_id = p.id
                        JOIN documents d ON p.document_id = d.id
                        WHERE d.slug = %s AND p.page_number = %s
                        LIMIT 1;
                    """, (doc_slug, p_num))
                    row = cur.fetchone()
                    if row:
                        results.append(FigureResult(
                            figure_id=row[0],
                            document_slug=doc_slug,
                            page_number=p_num,
                            caption=row[1],
                            description=row[2],
                            image_path=row[3],
                            score=round(chunk["dense_score"], 4)
                        ))
                return results

retriever = HybridRetriever()
