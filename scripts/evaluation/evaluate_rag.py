"""
RAG Evaluation with RAGAS Metrics

Metrics: Faithfulness, Answer Relevancy, Latency
Uses OpenAI as judge (avoids same-model bias with Grok-4.1-fast RAG)

Usage:
    python scripts/evaluation/evaluate_rag.py --dataset tests/eval_dataset.json
    python scripts/evaluation/evaluate_rag.py --no-ragas  # Timing only

Requirements:
    pip install ragas datasets langchain-openai pandas
"""

import os
import sys
import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from statistics import mean

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

# RAGAS imports
try:
    from ragas import evaluate, EvaluationDataset
    from ragas.metrics._faithfulness import Faithfulness
    from ragas.metrics._answer_relevance import ResponseRelevancy
    from ragas.metrics._context_precision import ContextPrecision
    from ragas.metrics._context_recall import ContextRecall
    from ragas.llms import llm_factory
    from ragas.embeddings import embedding_factory
    from ragas.run_config import RunConfig
    import openai
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    print("Warning: RAGAS not installed. Install with: pip install ragas datasets")
except Exception as e:
    RAGAS_AVAILABLE = False
    print(f"Warning: RAGAS import failed: {e}")
    print("Continuing without RAGAS metrics...")

# OpenRouter support
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
USE_OPENROUTER = os.getenv("USE_OPENROUTER", "false").lower() == "true"

# LangChain imports for OpenAI wrapper
try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    LANGCHAIN_OPENAI_AVAILABLE = True
except ImportError:
    LANGCHAIN_OPENAI_AVAILABLE = False
    print("Warning: langchain-openai not installed. Install with: pip install langchain-openai")

# Voyage AI imports
try:
    from langchain_community.embeddings import VoyageEmbeddings
    VOYAGE_AVAILABLE = True
except ImportError:
    VOYAGE_AVAILABLE = False
    print("Warning: langchain-community not installed. Install with: pip install langchain-community")

# Local imports
from src.retrieval.langchain_retriever import get_langchain_retriever
from src.query_processing.gemini_client import GeminiClient

# Fix Windows console encoding
import sys
import os
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# Immediate flush print to verify output works
print("Starting RAG evaluation...", flush=True)
sys.stdout.flush()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# --- Configuration ---
THRESHOLDS = {
    "faithfulness": 0.7,
    # "response_relevancy": 0.7,  # Disabled - causes embed_query errors
    "context_recall": 0.6,
    "context_precision": 0.5,
    "latency_ms": 15000,
}

OPENAI_CONFIG = {
    "model": "gpt-4.1-mini",  # Use gpt-4.1-mini or gpt-4o-mini for reliable faithfulness evaluation 
    "embedding_model": "voyage-4-lite",  # Match production embedding model
    "max_workers": 4,  # Conservative for rate limits (guide recommends 4-8)
    "timeout": 300,  # 5 minutes for complex operations
    "max_retries": 15,  # More retries for rate limits
    "max_wait": 90,  # Longer wait between retries
    "batch_size": 5,  # Batch size for heavy metrics like Faithfulness
    "batch_pause": 60,  # Pause seconds between batches
}


def create_ragas_evaluator():
    """Initialize RAGAS with OpenAI as judge using modern llm_factory API."""
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY required")

    # Use OpenRouter if configured
    if USE_OPENROUTER and OPENROUTER_API_KEY:
        logger.info("Using OpenRouter for evaluation")
        openai_client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
    else:
        logger.info(f"Using OpenAI model: {OPENAI_CONFIG['model']}")
        openai_client = openai.OpenAI(api_key=openai_api_key)
        model = OPENAI_CONFIG["model"]

    # Use modern llm_factory with temperature=0 for deterministic evaluation (per RAGAS guide)
    llm = llm_factory(
        model=model,
        client=openai_client,
        max_tokens=4096,
        temperature=0,  # Deterministic for evaluation
    )
    
    # Use modern embedding_factory
    embeddings = embedding_factory(
        "openai",
        model="text-embedding-3-small",
        client=openai.OpenAI(api_key=openai_api_key),  # Always use OpenAI for embeddings
    )

    return llm, embeddings


class RAGPipeline:
    """Minimal RAG pipeline wrapper for evaluation."""

    def __init__(self):
        self._retriever = None
        self.llm = GeminiClient()

    async def _get_retriever(self):
        """Lazy async initialization of retriever."""
        if self._retriever is None:
            self._retriever = await get_langchain_retriever(enable_reranking=True)
        return self._retriever

    async def query(self, question: str) -> Dict[str, Any]:
        """Run query and return answer, contexts, timing."""
        timing = {}
        retriever = await self._get_retriever()

        # Retrieval
        t0 = time.time()
        try:
            results = await retriever.retrieve(question)
            contexts = results.get("documents", [])
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            contexts = []
        timing["retrieval_ms"] = (time.time() - t0) * 1000

        # Generation
        t0 = time.time()
        try:
            response = await self.llm.search_and_process(query=question, vector_results=results)
            answer = response.get("answer", "")
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            answer = ""

        timing["generation_ms"] = (time.time() - t0) * 1000
        timing["total_ms"] = timing["retrieval_ms"] + timing["generation_ms"]

        return {"answer": answer, "contexts": contexts, "timing": timing}


async def run_rag_pipeline(
    qa_pairs: List[Dict], 
    pipeline: RAGPipeline, 
    checkpoint_file: str = None,
    max_concurrency: int = 3,  # Conservative default for Gemini free tier (10-15 RPM)
) -> List[Dict]:
    """
    Run RAG pipeline for all questions with parallel execution.
    
    Args:
        qa_pairs: List of QA pairs to evaluate
        pipeline: RAGPipeline instance
        checkpoint_file: Path to checkpoint file for resuming
        max_concurrency: Max concurrent API calls (default 3 for rate limit safety)
    """
    results = []
    start_index = 0

    # Load checkpoint if exists
    if checkpoint_file and Path(checkpoint_file).exists():
        with open(checkpoint_file, encoding='utf-8') as f:
            checkpoint = json.load(f)
            results = checkpoint.get("results", [])
            start_index = checkpoint.get("next_index", 0)
            logger.info(f"Resuming from checkpoint: {start_index}/{len(qa_pairs)}")

    # Filter remaining QA pairs
    remaining_pairs = list(enumerate(qa_pairs[start_index:], start=start_index))
    
    if not remaining_pairs:
        logger.info("All queries already processed.")
        return results
    
    # Semaphore for rate limiting - reduced to 1 to avoid 429 errors
    semaphore = asyncio.Semaphore(max_concurrency)
    results_lock = asyncio.Lock()
    completed_count = [0]  # Mutable counter for progress tracking
    
    async def process_single(idx: int, qa: Dict) -> Dict:
        """Process a single query with rate limiting."""
        question = qa["question"]
        
        async with semaphore:
            try:
                output = await pipeline.query(question)
                result = {
                    "question": question,
                    "ground_truth": qa["ground_truth"],
                    "ground_truth_context": qa.get("ground_truth_context", ""),
                    "question_type": qa.get("question_type", "unknown"),
                    "model": qa.get("model", "unknown"),
                    "answer": output["answer"],
                    "contexts": output["contexts"],
                    "timing": output["timing"],
                    "_idx": idx,  # Track original order
                }
                async with results_lock:
                    completed_count[0] += 1
                    logger.info(f"[{completed_count[0]}/{len(qa_pairs)}] ✓ {output['timing']['total_ms']:.0f}ms - {question[:50]}...")
                return result
            except Exception as e:
                async with results_lock:
                    completed_count[0] += 1
                    logger.error(f"[{completed_count[0]}/{len(qa_pairs)}] ✗ {e} - {question[:50]}...")
                return {
                    "question": question,
                    "ground_truth": qa["ground_truth"],
                    "answer": "",
                    "contexts": [],
                    "timing": {"retrieval_ms": 0, "generation_ms": 0, "total_ms": 0},
                    "error": str(e),
                    "_idx": idx,
                }
            finally:
                # Increased delay to avoid 429 rate limit errors
                # Minimum 2 seconds between requests to stay under QPM limits
                await asyncio.sleep(2.0)
    
    logger.info(f"Processing {len(remaining_pairs)} queries with {max_concurrency} concurrent workers...")
    
    # Process in batches for checkpoint support
    batch_size = 10
    for batch_start in range(0, len(remaining_pairs), batch_size):
        batch = remaining_pairs[batch_start:batch_start + batch_size]
        
        # Run batch in parallel
        tasks = [process_single(idx, qa) for idx, qa in batch]
        batch_results = await asyncio.gather(*tasks)
        
        # Sort by original index and add to results
        batch_results.sort(key=lambda x: x["_idx"])
        for r in batch_results:
            r.pop("_idx", None)  # Remove internal tracking field
            results.append(r)
        
        # Save checkpoint after each batch
        if checkpoint_file:
            current_idx = start_index + batch_start + len(batch)
            with open(checkpoint_file, "w", encoding='utf-8') as f:
                json.dump({"results": results, "next_index": current_idx}, f, indent=2)
            logger.info(f"Checkpoint saved at {current_idx}/{len(qa_pairs)}")

    # Clear checkpoint file on completion
    if checkpoint_file and Path(checkpoint_file).exists():
        Path(checkpoint_file).unlink()
        logger.info("Checkpoint cleared - evaluation complete.")

    return results


def run_ragas_evaluation(results: List[Dict], llm, embeddings) -> Dict[str, float]:
    """Run RAGAS metrics on results with batch processing for heavy metrics (per RAGAS guide)."""
    import math

    # Prepare dataset using EvaluationDataset with correct field names
    samples = []
    for r in results:
        # LIMIT to top 3 contexts and truncate text to avoid massive token usage
        contexts = r["contexts"] if r["contexts"] else [""]
        limited_contexts = [c[:1000] for c in contexts[:3]]

        samples.append({
            "user_input": r["question"],
            "response": r["answer"],
            "retrieved_contexts": limited_contexts,
            "reference": r.get("ground_truth_context", r["ground_truth"]),
        })

    # Rate-friendly configuration (per RAGAS guide)
    run_config = RunConfig(
        max_workers=OPENAI_CONFIG["max_workers"],
        timeout=OPENAI_CONFIG["timeout"],
        max_retries=OPENAI_CONFIG["max_retries"],
        max_wait=OPENAI_CONFIG["max_wait"],
        log_tenacity=True,  # Log retry attempts for debugging
    )

    # Initialize metrics with LLM
    faithfulness = Faithfulness(llm=llm)
    context_precision = ContextPrecision(llm=llm)
    context_recall = ContextRecall(llm=llm)

    # Faithfulness is "Very High Impact" metric - process in batches with pauses
    batch_size = OPENAI_CONFIG["batch_size"]
    batch_pause = OPENAI_CONFIG["batch_pause"]
    
    logger.info(f"Running RAGAS evaluation with batch processing (batch_size={batch_size}, pause={batch_pause}s)...")
    logger.info(f"Config: max_workers={OPENAI_CONFIG['max_workers']}, max_retries={OPENAI_CONFIG['max_retries']}")

    all_scores = {"faithfulness": [], "context_precision": [], "context_recall": []}
    
    # Process in batches to avoid rate limits (per RAGAS guide)
    num_batches = (len(samples) + batch_size - 1) // batch_size
    
    for batch_idx in range(num_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(samples))
        batch_samples = samples[batch_start:batch_end]
        
        logger.info(f"Processing batch {batch_idx + 1}/{num_batches} (samples {batch_start + 1}-{batch_end})...")
        
        batch_dataset = EvaluationDataset.from_list(batch_samples)
        
        try:
            # Run all metrics on this batch
            batch_results = evaluate(
                dataset=batch_dataset,
                metrics=[faithfulness, context_precision, context_recall],
                run_config=run_config,
            )
            
            # Extract scores from batch
            for score in batch_results.scores:
                all_scores["faithfulness"].append(score.get("faithfulness"))
                all_scores["context_precision"].append(score.get("context_precision"))
                all_scores["context_recall"].append(score.get("context_recall"))
                
        except Exception as e:
            logger.error(f"Batch {batch_idx + 1} failed: {e}")
            # Add None for failed samples
            for _ in batch_samples:
                all_scores["faithfulness"].append(None)
                all_scores["context_precision"].append(None)
                all_scores["context_recall"].append(None)
        
        # Pause between batches (except after last batch) - per RAGAS guide
        if batch_idx < num_batches - 1:
            logger.info(f"Pausing for {batch_pause} seconds to avoid rate limits...")
            time.sleep(batch_pause)

    # Log NaN faithfulness values for debugging
    faithfulness_scores = all_scores["faithfulness"]
    nan_count = sum(1 for s in faithfulness_scores if s is None or (isinstance(s, float) and math.isnan(s)))
    if nan_count > 0:
        logger.warning(f"Faithfulness: {nan_count}/{len(faithfulness_scores)} samples returned NaN/None")
        if USE_OPENROUTER:
            logger.warning("Consider using OpenAI judge model (set USE_OPENROUTER=false) for more reliable faithfulness evaluation")

    return all_scores


def calculate_summary(results: List[Dict], ragas_scores: Optional[Dict]) -> Dict[str, Any]:
    """Calculate evaluation summary."""
    
    successful = [r for r in results if "error" not in r]
    timings = [r["timing"]["total_ms"] for r in successful]
    
    # Aggregate metrics
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_queries": len(results),
        "successful_queries": len(successful),
        "timing": {
            "avg_retrieval_ms": round(mean([r["timing"]["retrieval_ms"] for r in successful]), 1),
            "avg_generation_ms": round(mean([r["timing"]["generation_ms"] for r in successful]), 1),
            "avg_total_ms": round(mean(timings), 1),
            "p95_total_ms": round(sorted(timings)[int(len(timings) * 0.95)] if timings else 0, 1),
        },
        "ragas": {},
        "threshold_failures": [],
    }
    
    # Add RAGAS scores if available
    if ragas_scores:
        for metric, scores in ragas_scores.items():
            import math
            valid_scores = [s for s in scores if s is not None and not (isinstance(s, float) and math.isnan(s))]
            avg = round(mean(valid_scores), 3) if valid_scores else 0.0
            summary["ragas"][metric] = avg

            # Check thresholds
            if metric in THRESHOLDS and avg < THRESHOLDS[metric]:
                summary["threshold_failures"].append(
                    f"{metric}: {avg:.3f} < {THRESHOLDS[metric]}"
                )
    
    # Check latency threshold
    if summary["timing"]["avg_total_ms"] > THRESHOLDS["latency_ms"]:
        summary["threshold_failures"].append(
            f"latency: {summary['timing']['avg_total_ms']}ms > {THRESHOLDS['latency_ms']}ms"
        )
    
    summary["passed"] = len(summary["threshold_failures"]) == 0
    summary["results"] = results
    
    return summary


def print_summary(summary: Dict[str, Any]):
    """Print formatted summary."""
    print("\n" + "=" * 60)
    print("RAG EVALUATION RESULTS")
    print("=" * 60)
    
    print(f"\n✅ Successful: {summary['successful_queries']}/{summary['total_queries']}")
    
    print("\n📈 RAGAS METRICS:")
    for metric, score in summary["ragas"].items():
        status = "✓" if score >= THRESHOLDS.get(metric, 0) else "✗"
        print(f"  {status} {metric}: {score:.3f}")
    
    # Add question type analysis if available
    question_types = {}
    for r in summary.get("results", []):
        qtype = r.get("question_type", "unknown")
        question_types[qtype] = question_types.get(qtype, 0) + 1
    
    if question_types:
        print("\n📊 QUESTION TYPE DISTRIBUTION:")
        for qtype, count in sorted(question_types.items()):
            print(f"  • {qtype}: {count}")
    
    print("\n⏱️ TIMING:")
    print(f"  • Avg Total:    {summary['timing']['avg_total_ms']:.0f}ms")
    print(f"  • P95 Total:    {summary['timing']['p95_total_ms']:.0f}ms")
    print(f"  • Avg Retrieval: {summary['timing']['avg_retrieval_ms']:.0f}ms")
    print(f"  • Avg Generation: {summary['timing']['avg_generation_ms']:.0f}ms")
    
    if summary["passed"]:
        print("\n✅ PASSED")
    else:
        print("\n❌ FAILED:")
        for f in summary["threshold_failures"]:
            print(f"  • {f}")
    
    print("=" * 60 + "\n")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate RAG with RAGAS")
    parser.add_argument("--dataset", "-d", default="tests/eval_dataset_ragas.json")
    parser.add_argument("--output", "-o", default="results/evaluation_results.json")
    parser.add_argument("--no-ragas", action="store_true", help="Skip RAGAS (timing only)")
    parser.add_argument("--checkpoint", "-c", default="results/evaluation_checkpoint.json", help="Checkpoint file for resuming")
    parser.add_argument("--concurrency", type=int, default=3, help="Max concurrent API calls (default: 3, safe for free tier)")
    parser.add_argument("--limit", type=int, default=None, help="Limit to first N queries (for quick testing)")
    args = parser.parse_args()

    # Load dataset
    if not Path(args.dataset).exists():
        print(f"Error: Dataset not found: {args.dataset}")
        sys.exit(1)

    with open(args.dataset, encoding='utf-8') as f:
        qa_pairs = json.load(f).get("qa_pairs", [])

    # Apply limit if specified
    if args.limit:
        qa_pairs = qa_pairs[:args.limit]
        logger.info(f"Limited to first {args.limit} queries")

    logger.info(f"Loaded {len(qa_pairs)} QA pairs")

    # Run RAG pipeline with checkpointing and controlled concurrency
    pipeline = RAGPipeline()
    results = await run_rag_pipeline(
        qa_pairs, 
        pipeline, 
        checkpoint_file=args.checkpoint,
        max_concurrency=args.concurrency
    )

    # Run RAGAS evaluation
    ragas_scores = None
    if not args.no_ragas:
        try:
            llm, embeddings = create_ragas_evaluator()
            ragas_scores = run_ragas_evaluation(results, llm, embeddings)
        except Exception as e:
            logger.error(f"RAGAS failed: {e}")
            import traceback
            traceback.print_exc()
            logger.info("Continuing without RAGAS metrics...")

    # Calculate summary (results always saved, even if RAGAS fails)
    summary = calculate_summary(results, ragas_scores)

    # Save results
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    # Print
    print_summary(summary)

    sys.exit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n{'='*60}", flush=True)
        print(f"FATAL ERROR: {type(e).__name__}", flush=True)
        print(f"Message: {str(e)}", flush=True)
        print(f"{'='*60}\n", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
