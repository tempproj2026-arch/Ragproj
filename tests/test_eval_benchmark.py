import json
import time
from pathlib import Path
from typing import Dict, List, Any

from ragcore.config import settings
from ragcore.logging import get_logger
from ragcore.retriever import retriever

logger = get_logger("tests.benchmark")

def run_evaluation(eval_path: str = "data/dev/questions/eval_questions.json"):
    path = Path(eval_path)
    if not path.exists():
        raise FileNotFoundError(f"Evaluation file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print("==================================================================")
    print(f"      RUNNING RETRIEVAL EVALUATION ON {len(questions)} BENCHMARK QUESTIONS       ")
    print("==================================================================\n")

    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    reciprocal_ranks = []

    type_stats: Dict[str, Dict[str, Any]] = {}

    start_time = time.time()

    for idx, q in enumerate(questions, start=1):
        q_id = q.get("id", f"q{idx}")
        question = q["question"]
        expected_book = q.get("target_book", "").replace(".pdf", "").strip()
        expected_page = q.get("target_page")
        content_type = q.get("content_type", "text")

        if content_type not in type_stats:
            type_stats[content_type] = {"total": 0, "hit1": 0, "hit3": 0, "hit5": 0, "rr": []}
        type_stats[content_type]["total"] += 1

        # Retrieve top 5 hybrid candidates
        results = retriever.search_hybrid(
            query=question,
            top_k=5,
            use_reranker=True
        )

        matched_rank = None
        for rank, res in enumerate(results, start=1):
            if res.document_slug == expected_book and res.page_number == expected_page:
                matched_rank = rank
                break

        # If not found in hybrid text and question is looking for a figure, check search_figures
        if matched_rank is None and content_type == "figure":
            fig_results = retriever.search_figures(question, top_k=5)
            for rank, fres in enumerate(fig_results, start=1):
                if fres.document_slug == expected_book and fres.page_number == expected_page:
                    matched_rank = rank
                    break

        if matched_rank is not None:
            if matched_rank == 1:
                hit_at_1 += 1
                type_stats[content_type]["hit1"] += 1
            if matched_rank <= 3:
                hit_at_3 += 1
                type_stats[content_type]["hit3"] += 1
            if matched_rank <= 5:
                hit_at_5 += 1
                type_stats[content_type]["hit5"] += 1
            rr = 1.0 / matched_rank
            reciprocal_ranks.append(rr)
            type_stats[content_type]["rr"].append(rr)
            status = f"PASS (Rank {matched_rank})"
        else:
            reciprocal_ranks.append(0.0)
            type_stats[content_type]["rr"].append(0.0)
            status = "MISS (Not in Top-5)"

        print(f"[{idx:02d}/{len(questions)}] {q_id} [{content_type.upper():7s}] Target: {expected_book} p.{expected_page} -> {status}")
        if matched_rank is None:
            top_found = [f"p.{r.page_number} ({r.document_slug})" for r in results[:2]]
            print(f"      Top retrieved: {top_found}")

    total = len(questions)
    elapsed = time.time() - start_time
    mrr = sum(reciprocal_ranks) / total if total > 0 else 0.0

    print("\n==================================================================")
    print("                     EVALUATION RESULTS SUMMARY                   ")
    print("==================================================================")
    print(f"Total Questions Evaluated: {total}")
    print(f"Total Time Taken:          {elapsed:.2f}s ({elapsed/total:.2f}s / query)")
    print(f"Hit@1  (Top-1 Accuracy):   {hit_at_1}/{total} ({hit_at_1/total*100:.1f}%)")
    print(f"Hit@3  (Top-3 Recall):     {hit_at_3}/{total} ({hit_at_3/total*100:.1f}%)")
    print(f"Hit@5  (Top-5 Recall):     {hit_at_5}/{total} ({hit_at_5/total*100:.1f}%)")
    print(f"MRR    (Mean Recip. Rank): {mrr:.4f}")
    print("------------------------------------------------------------------")
    print(f"{'Content Type':<15} | {'Count':<6} | {'Hit@1':<8} | {'Hit@3':<8} | {'Hit@5':<8} | {'MRR':<8}")
    print("------------------------------------------------------------------")
    for ctype, s in sorted(type_stats.items()):
        c_tot = s["total"]
        c_h1 = s["hit1"] / c_tot * 100
        c_h3 = s["hit3"] / c_tot * 100
        c_h5 = s["hit5"] / c_tot * 100
        c_mrr = sum(s["rr"]) / c_tot if c_tot > 0 else 0.0
        print(f"{ctype:<15} | {c_tot:<6} | {c_h1:>6.1f}% | {c_h3:>6.1f}% | {c_h5:>6.1f}% | {c_mrr:>6.4f}")
    print("==================================================================\n")

if __name__ == "__main__":
    run_evaluation()
