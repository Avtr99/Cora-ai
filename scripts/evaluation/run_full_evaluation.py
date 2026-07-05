"""
Full RAG Evaluation Pipeline

Convenience script that runs both dataset generation and evaluation
in a single command. Useful for CI/CD integration.

Usage:
    python scripts/evaluation/run_full_evaluation.py
    python scripts/evaluation/run_full_evaluation.py --num-samples 50
    python scripts/evaluation/run_full_evaluation.py --skip-generation  # Use existing dataset
"""

import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from scripts.evaluation.generate_qa_hybrid import generate_qa_dataset as generate_eval_dataset
from scripts.evaluation.evaluate_rag import run_ragas_evaluation, print_summary


async def run_full_evaluation(
    num_samples: int = 30,
    skip_generation: bool = False,
    dataset_path: str = "tests/eval_dataset_generated.json",
    results_path: str = "results/evaluation_results.json",
    collection_name: str = "cora_dense_only"
) -> bool:
    """
    Run the complete evaluation pipeline.
    
    Args:
        num_samples: Number of QA pairs to generate
        skip_generation: Skip dataset generation (use existing)
        dataset_path: Path to dataset file
        results_path: Path to save results
        collection_name: Qdrant collection to sample from
        
    Returns:
        True if evaluation passed all thresholds
    """
    print("\n" + "=" * 70)
    print("CORA RAG EVALUATION PIPELINE")
    print("=" * 70)
    print(f"Started: {datetime.utcnow().isoformat()}")
    print(f"Collection: {collection_name}")
    print(f"Samples: {num_samples}")
    print("=" * 70 + "\n")
    
    # Step 1: Generate dataset (unless skipped)
    if not skip_generation:
        print("📝 STEP 1: Generating Evaluation Dataset")
        print("-" * 50)
        
        try:
            dataset = await generate_eval_dataset(
                num_samples=num_samples,
                output_path=dataset_path,
                collection_name=collection_name
            )
            print(f"✅ Generated {dataset.num_samples} QA pairs\n")
        except Exception as e:
            print(f"❌ Dataset generation failed: {e}")
            return False
    else:
        print("⏭️ STEP 1: Skipping dataset generation (using existing)")
        if not Path(dataset_path).exists():
            print(f"❌ Dataset not found at {dataset_path}")
            return False
        print(f"✅ Using existing dataset: {dataset_path}\n")
    
    # Step 2: Run evaluation
    print("🔍 STEP 2: Running RAG Evaluation")
    print("-" * 50)
    
    try:
        summary = await run_ragas_evaluation(
            dataset_path=dataset_path,
            output_path=results_path,
            use_ragas=True
        )
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        return False
    
    # Print results
    print_summary(summary)
    
    # Save summary report
    report_path = Path(results_path).parent / "evaluation_report.txt"
    with open(report_path, "w") as f:
        f.write("CORA RAG Evaluation Report\n")
        f.write(f"Generated: {summary.timestamp}\n")
        f.write(f"Dataset: {summary.dataset_path}\n\n")
        f.write("RAGAS Metrics:\n")
        f.write(f"  Faithfulness: {summary.avg_faithfulness:.3f}\n")
        f.write(f"  Answer Relevancy: {summary.avg_answer_relevancy:.3f}\n")
        f.write(f"  Context Recall: {summary.avg_context_recall:.3f}\n")
        f.write(f"  Context Precision: {summary.avg_context_precision:.3f}\n\n")
        f.write("Timing:\n")
        f.write(f"  Avg Total: {summary.avg_total_ms:.0f}ms\n")
        f.write(f"  P95 Total: {summary.p95_total_ms:.0f}ms\n\n")
        f.write(f"Result: {'PASSED' if summary.passed else 'FAILED'}\n")
        if summary.threshold_failures:
            f.write("Failures:\n")
            for failure in summary.threshold_failures:
                f.write(f"  - {failure}\n")
    
    print(f"📄 Report saved to: {report_path}")
    
    return summary.passed


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run full RAG evaluation pipeline"
    )
    parser.add_argument(
        "--num-samples", "-n",
        type=int,
        default=30,
        help="Number of QA pairs to generate (default: 30)"
    )
    parser.add_argument(
        "--skip-generation",
        action="store_true",
        help="Skip dataset generation, use existing dataset"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/eval_dataset_generated.json",
        help="Dataset file path"
    )
    parser.add_argument(
        "--results",
        type=str,
        default="results/evaluation_results.json",
        help="Results output path"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="cora_dense_only",
        help="Qdrant collection name"
    )
    
    args = parser.parse_args()
    
    # Ensure results directory exists
    Path(args.results).parent.mkdir(parents=True, exist_ok=True)
    
    # Run evaluation
    passed = asyncio.run(run_full_evaluation(
        num_samples=args.num_samples,
        skip_generation=args.skip_generation,
        dataset_path=args.dataset,
        results_path=args.results,
        collection_name=args.collection
    ))
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
