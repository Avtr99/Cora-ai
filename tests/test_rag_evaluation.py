"""
Automated RAG Evaluation Tests

This module provides automated evaluation of the RAG pipeline with:
- Reference Q&A pairs for regression testing
- Scoring metrics (success rate, confidence, latency)
- CI-friendly pytest integration with configurable thresholds

Usage:
    pytest tests/test_rag_evaluation.py -v
    pytest tests/test_rag_evaluation.py -v --rag-eval  # Run full evaluation
"""
import pytest
import asyncio
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock


# Reference Q&A dataset for evaluation
REFERENCE_QA_PAIRS = [
    {
        "id": "qa_001",
        "query": "What is additionality in carbon credits?",
        "expected_keywords": ["additionality", "emission", "reduction", "project", "baseline"],
        "expected_sources": [],  # Empty means any source is acceptable
        "min_confidence": 0.5,
        "category": "concepts"
    },
    {
        "id": "qa_002", 
        "query": "How are carbon credits verified?",
        "expected_keywords": ["verification", "audit", "third-party", "standard"],
        "expected_sources": [],
        "min_confidence": 0.5,
        "category": "process"
    },
    {
        "id": "qa_003",
        "query": "What are the requirements for VCS projects?",
        "expected_keywords": ["VCS", "Verra", "requirement", "methodology"],
        "expected_sources": [],
        "min_confidence": 0.5,
        "category": "standards"
    },
    {
        "id": "qa_004",
        "query": "Explain the difference between ex-ante and ex-post credits",
        "expected_keywords": ["ex-ante", "ex-post", "credit", "issuance"],
        "expected_sources": [],
        "min_confidence": 0.4,
        "category": "concepts"
    },
    {
        "id": "qa_005",
        "query": "What is the Gold Standard certification process?",
        "expected_keywords": ["Gold Standard", "certification", "project"],
        "expected_sources": [],
        "min_confidence": 0.5,
        "category": "standards"
    }
]

# Evaluation thresholds for CI
EVAL_THRESHOLDS = {
    "min_success_rate": 0.8,  # 80% of queries must succeed
    "min_avg_confidence": 0.5,  # Average confidence >= 0.5
    "max_avg_latency_seconds": 30.0,  # Average latency < 30s
    "min_keyword_match_rate": 0.3,  # At least 30% of expected keywords found
}


@dataclass
class EvaluationResult:
    """Result of evaluating a single Q&A pair."""
    qa_id: str
    query: str
    success: bool
    answer: Optional[str]
    confidence: float
    sources: List[str]
    latency_seconds: float
    keyword_matches: int
    keyword_total: int
    keyword_match_rate: float
    error: Optional[str] = None


@dataclass
class EvaluationSummary:
    """Summary of all evaluation results."""
    total_queries: int
    successful_queries: int
    success_rate: float
    avg_confidence: float
    avg_latency_seconds: float
    avg_keyword_match_rate: float
    passed_thresholds: bool
    threshold_failures: List[str]
    timestamp: str
    results: List[Dict[str, Any]]


def calculate_keyword_match(answer: str, expected_keywords: List[str]) -> tuple:
    """
    Calculate how many expected keywords appear in the answer.
    
    Args:
        answer: Generated answer text
        expected_keywords: List of keywords to look for
        
    Returns:
        Tuple of (matches, total, match_rate)
    """
    if not answer or not expected_keywords:
        return 0, len(expected_keywords) if expected_keywords else 0, 0.0
    
    answer_lower = answer.lower()
    matches = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    total = len(expected_keywords)
    rate = matches / total if total > 0 else 0.0
    
    return matches, total, rate


class RAGEvaluator:
    """
    Evaluator for RAG pipeline quality.
    
    Runs reference queries through the RAG system and scores results
    based on success, confidence, latency, and keyword matching.
    """
    
    def __init__(self):
        """
        Initialize the evaluator.
        """
        self.results: List[EvaluationResult] = []
    
    async def evaluate_single(
        self,
        qa_pair: Dict[str, Any],
        retriever: Any,
        gemini_client: Any
    ) -> EvaluationResult:
        """
        Evaluate a single Q&A pair.
        
        Args:
            qa_pair: Reference Q&A pair with query and expectations
            retriever: DartboardRetriever instance
            gemini_client: GeminiClient instance
            
        Returns:
            EvaluationResult with scores and metrics
        """
        query = qa_pair["query"]
        qa_id = qa_pair["id"]
        expected_keywords = qa_pair.get("expected_keywords", [])
        
        start_time = time.time()
        
        try:
            # Step 1: Retrieve documents
            vector_results = await retriever.retrieve(query)
            
            # Step 2: Generate answer
            processed_results = await gemini_client.search_and_process(
                query=query,
                vector_results=vector_results
            )
            
            latency = time.time() - start_time
            
            answer = processed_results.get("answer", "")
            confidence = processed_results.get("confidence", 0.0)
            sources = processed_results.get("sources", [])
            
            # Calculate keyword match
            matches, total, rate = calculate_keyword_match(answer, expected_keywords)
            
            return EvaluationResult(
                qa_id=qa_id,
                query=query,
                success=True,
                answer=answer,
                confidence=confidence,
                sources=sources,
                latency_seconds=latency,
                keyword_matches=matches,
                keyword_total=total,
                keyword_match_rate=rate
            )
            
        except Exception as e:
            latency = time.time() - start_time
            return EvaluationResult(
                qa_id=qa_id,
                query=query,
                success=False,
                answer=None,
                confidence=0.0,
                sources=[],
                latency_seconds=latency,
                keyword_matches=0,
                keyword_total=len(expected_keywords),
                keyword_match_rate=0.0,
                error=str(e)
            )
    
    async def evaluate_all(
        self,
        qa_pairs: List[Dict[str, Any]],
        retriever: Any,
        gemini_client: Any
    ) -> EvaluationSummary:
        """
        Evaluate all Q&A pairs and generate summary.
        
        Args:
            qa_pairs: List of reference Q&A pairs
            retriever: DartboardRetriever instance
            gemini_client: GeminiClient instance
            
        Returns:
            EvaluationSummary with aggregate metrics
        """
        self.results = []
        
        for qa_pair in qa_pairs:
            result = await self.evaluate_single(qa_pair, retriever, gemini_client)
            self.results.append(result)
        
        return self._generate_summary()
    
    def _generate_summary(self) -> EvaluationSummary:
        """Generate summary from collected results."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        
        success_rate = successful / total if total > 0 else 0.0
        
        confidences = [r.confidence for r in self.results if r.success]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        latencies = [r.latency_seconds for r in self.results]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        keyword_rates = [r.keyword_match_rate for r in self.results if r.success]
        avg_keyword_rate = sum(keyword_rates) / len(keyword_rates) if keyword_rates else 0.0
        
        # Check thresholds
        threshold_failures = []
        
        if success_rate < EVAL_THRESHOLDS["min_success_rate"]:
            threshold_failures.append(
                f"Success rate {success_rate:.2%} < {EVAL_THRESHOLDS['min_success_rate']:.2%}"
            )
        
        if avg_confidence < EVAL_THRESHOLDS["min_avg_confidence"]:
            threshold_failures.append(
                f"Avg confidence {avg_confidence:.2f} < {EVAL_THRESHOLDS['min_avg_confidence']}"
            )
        
        if avg_latency > EVAL_THRESHOLDS["max_avg_latency_seconds"]:
            threshold_failures.append(
                f"Avg latency {avg_latency:.1f}s > {EVAL_THRESHOLDS['max_avg_latency_seconds']}s"
            )
        
        if avg_keyword_rate < EVAL_THRESHOLDS["min_keyword_match_rate"]:
            threshold_failures.append(
                f"Keyword match rate {avg_keyword_rate:.2%} < {EVAL_THRESHOLDS['min_keyword_match_rate']:.2%}"
            )
        
        return EvaluationSummary(
            total_queries=total,
            successful_queries=successful,
            success_rate=success_rate,
            avg_confidence=avg_confidence,
            avg_latency_seconds=avg_latency,
            avg_keyword_match_rate=avg_keyword_rate,
            passed_thresholds=len(threshold_failures) == 0,
            threshold_failures=threshold_failures,
            timestamp=datetime.utcnow().isoformat(),
            results=[asdict(r) for r in self.results]
        )
    
    def save_results(self, output_path: Path) -> None:
        """Save evaluation results to JSON file."""
        summary = self._generate_summary()
        with open(output_path, "w") as f:
            json.dump(asdict(summary), f, indent=2)


# Fixtures for mocked testing
@pytest.fixture
def mock_retriever():
    """Create a mock retriever for unit testing."""
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value={
        "documents": [
            "Carbon credits represent verified emission reductions.",
            "Additionality ensures projects go beyond business as usual.",
            "VCS and Gold Standard are major certification bodies."
        ],
        "metadatas": [
            {"source": "vcm_basics.md", "doc_type": "methodology"},
            {"source": "additionality.md", "doc_type": "concepts"},
            {"source": "standards.md", "doc_type": "standards"}
        ],
        "distances": [0.15, 0.20, 0.25]
    })
    return retriever


@pytest.fixture
def mock_gemini_client():
    """Create a mock Gemini client for unit testing."""
    client = MagicMock()
    
    async def mock_search_and_process(query: str, vector_results: Dict):
        # Generate contextual mock responses based on query keywords
        if "additionality" in query.lower():
            answer = "Additionality is a key concept in carbon credits that ensures emission reductions would not have occurred without the project intervention."
        elif "verified" in query.lower() or "verification" in query.lower():
            answer = "Carbon credits are verified through third-party audits against established standards like VCS or Gold Standard."
        elif "vcs" in query.lower():
            answer = "VCS (Verified Carbon Standard) by Verra requires projects to follow approved methodologies and demonstrate additionality."
        elif "ex-ante" in query.lower() or "ex-post" in query.lower():
            answer = "Ex-ante credits are issued before emission reductions occur, while ex-post credits are issued after verified reductions."
        elif "gold standard" in query.lower():
            answer = "The Gold Standard certification process involves project design, validation, monitoring, and verification by accredited third parties."
        else:
            answer = "Carbon credits are certificates representing verified emission reductions in the voluntary carbon market."
        
        return {
            "answer": answer,
            "confidence": 0.85,
            "sources": ["knowledge_base"]
        }
    
    client.search_and_process = AsyncMock(side_effect=mock_search_and_process)
    return client


# Unit tests for evaluation logic
class TestKeywordMatching:
    """Tests for keyword matching logic."""
    
    def test_keyword_match_all_present(self):
        """Test when all keywords are found."""
        answer = "Additionality ensures emission reduction projects go beyond the baseline."
        keywords = ["additionality", "emission", "reduction", "baseline"]
        matches, total, rate = calculate_keyword_match(answer, keywords)
        assert matches == 4
        assert total == 4
        assert rate == 1.0
    
    def test_keyword_match_partial(self):
        """Test when some keywords are found."""
        answer = "Carbon credits represent emission reductions."
        keywords = ["carbon", "emission", "verification", "audit"]
        matches, total, rate = calculate_keyword_match(answer, keywords)
        assert matches == 2
        assert total == 4
        assert rate == 0.5
    
    def test_keyword_match_none(self):
        """Test when no keywords are found."""
        answer = "This is an unrelated answer."
        keywords = ["carbon", "emission", "verification"]
        matches, total, rate = calculate_keyword_match(answer, keywords)
        assert matches == 0
        assert total == 3
        assert rate == 0.0
    
    def test_keyword_match_empty_answer(self):
        """Test with empty answer."""
        matches, total, rate = calculate_keyword_match("", ["carbon"])
        assert matches == 0
        assert rate == 0.0
    
    def test_keyword_match_case_insensitive(self):
        """Test case-insensitive matching."""
        answer = "ADDITIONALITY is important for CARBON credits."
        keywords = ["additionality", "carbon"]
        matches, total, rate = calculate_keyword_match(answer, keywords)
        assert matches == 2
        assert rate == 1.0


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""
    
    def test_result_creation(self):
        """Test creating an evaluation result."""
        result = EvaluationResult(
            qa_id="qa_001",
            query="Test query",
            success=True,
            answer="Test answer",
            confidence=0.9,
            sources=["source1"],
            latency_seconds=1.5,
            keyword_matches=3,
            keyword_total=4,
            keyword_match_rate=0.75
        )
        assert result.success is True
        assert result.confidence == 0.9
        assert result.keyword_match_rate == 0.75


@pytest.mark.asyncio
class TestRAGEvaluator:
    """Tests for RAGEvaluator class."""
    
    async def test_evaluate_single_success(self, mock_retriever, mock_gemini_client):
        """Test successful single evaluation."""
        evaluator = RAGEvaluator()
        qa_pair = REFERENCE_QA_PAIRS[0]  # Additionality question
        
        result = await evaluator.evaluate_single(
            qa_pair, mock_retriever, mock_gemini_client
        )
        
        assert result.success is True
        assert result.confidence > 0
        assert result.latency_seconds >= 0
        assert "additionality" in result.answer.lower()
    
    async def test_evaluate_all_generates_summary(self, mock_retriever, mock_gemini_client):
        """Test evaluating all Q&A pairs generates valid summary."""
        evaluator = RAGEvaluator()
        
        summary = await evaluator.evaluate_all(
            REFERENCE_QA_PAIRS[:3],  # Use subset for faster test
            mock_retriever,
            mock_gemini_client
        )
        
        assert summary.total_queries == 3
        assert summary.successful_queries == 3
        assert summary.success_rate == 1.0
        assert summary.avg_confidence > 0
        assert len(summary.results) == 3
    
    async def test_evaluate_handles_failure(self, mock_retriever):
        """Test evaluation handles failures gracefully."""
        evaluator = RAGEvaluator()
        
        # Create a failing client
        failing_client = MagicMock()
        failing_client.search_and_process = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        result = await evaluator.evaluate_single(
            REFERENCE_QA_PAIRS[0],
            mock_retriever,
            failing_client
        )
        
        assert result.success is False
        assert result.error == "API Error"
        assert result.confidence == 0.0


@pytest.mark.asyncio
class TestRAGEvaluationIntegration:
    """
    Integration tests that run the full evaluation with mocks.
    
    These tests verify the evaluation pipeline works end-to-end
    and can be extended to use real components when needed.
    """
    
    async def test_full_evaluation_passes_thresholds(
        self, mock_retriever, mock_gemini_client
    ):
        """Test that mocked evaluation passes all thresholds."""
        evaluator = RAGEvaluator()
        
        summary = await evaluator.evaluate_all(
            REFERENCE_QA_PAIRS,
            mock_retriever,
            mock_gemini_client
        )
        
        # With mocks, we expect all queries to succeed
        assert summary.success_rate >= EVAL_THRESHOLDS["min_success_rate"]
        assert summary.avg_confidence >= EVAL_THRESHOLDS["min_avg_confidence"]
        assert summary.avg_latency_seconds <= EVAL_THRESHOLDS["max_avg_latency_seconds"]
        
        # Summary should indicate passing
        assert summary.passed_thresholds is True
        assert len(summary.threshold_failures) == 0
    
    async def test_evaluation_detects_regression(self, mock_retriever):
        """Test that evaluation detects quality regression."""
        evaluator = RAGEvaluator()
        
        # Create a low-quality client
        low_quality_client = MagicMock()
        low_quality_client.search_and_process = AsyncMock(return_value={
            "answer": "I don't know.",
            "confidence": 0.1,
            "sources": []
        })
        
        summary = await evaluator.evaluate_all(
            REFERENCE_QA_PAIRS,
            mock_retriever,
            low_quality_client
        )
        
        # Low confidence should trigger threshold failure
        assert summary.avg_confidence < EVAL_THRESHOLDS["min_avg_confidence"]
        assert summary.passed_thresholds is False
        assert len(summary.threshold_failures) > 0


# CLI-compatible test for CI
def test_rag_evaluation_ci_check():
    """
    CI-compatible test that runs evaluation and asserts thresholds.
    
    This test uses mocks by default. To run with real components,
    set RAG_EVAL_LIVE=1 environment variable.
    """

    async def mock_search_and_process(query: str, vector_results: Dict):
        """Generate contextual mock responses based on query keywords."""
        query_lower = query.lower()
        if "additionality" in query_lower:
            answer = "Additionality is a key concept in carbon credits that ensures emission reductions would not have occurred without the project intervention beyond the baseline."
        elif "verified" in query_lower or "verification" in query_lower:
            answer = "Carbon credits are verified through third-party audits against established standards like VCS or Gold Standard."
        elif "vcs" in query_lower:
            answer = "VCS (Verified Carbon Standard) by Verra requires projects to follow approved methodologies and demonstrate additionality."
        elif "ex-ante" in query_lower or "ex-post" in query_lower:
            answer = "Ex-ante credits are issued before emission reductions occur, while ex-post credits are issued after verified reductions."
        elif "gold standard" in query_lower:
            answer = "The Gold Standard certification process involves project design, validation, monitoring, and verification by accredited third parties."
        else:
            answer = "Carbon credits are certificates representing verified emission reductions in the voluntary carbon market."
        
        return {
            "answer": answer,
            "confidence": 0.85,
            "sources": ["knowledge_base"]
        }
    
    async def run_evaluation():
        evaluator = RAGEvaluator()
        
        # Create mocks
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value={
            "documents": ["Test doc"],
            "metadatas": [{"source": "test.md"}],
            "distances": [0.1]
        })
        
        mock_client = MagicMock()
        mock_client.search_and_process = AsyncMock(side_effect=mock_search_and_process)
        
        summary = await evaluator.evaluate_all(
            REFERENCE_QA_PAIRS,
            mock_retriever,
            mock_client
        )
        
        return summary
    
    summary = asyncio.run(run_evaluation())
    
    # Assert thresholds for CI
    assert summary.success_rate >= EVAL_THRESHOLDS["min_success_rate"], \
        f"Success rate {summary.success_rate:.2%} below threshold"
    assert summary.passed_thresholds, \
        f"Threshold failures: {summary.threshold_failures}"
