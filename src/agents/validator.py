"""
Answer Validator Agent

Validates that generated answers are grounded in the provided sources.
This is an optional step that can be skipped for speed when confidence is high.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

# Limits used during validation prompts and quick checks
SHORT_ANSWER_CHAR_LIMIT = 100
SHORT_RELEVANCE_ANSWER_CHAR_LIMIT = 50
MAX_VALIDATION_SOURCES = 5
SOURCE_SNIPPET_MAX_CHARS = 1500
ANSWER_VALIDATION_MAX_CHARS = 2000
RELEVANCE_QUERY_MAX_CHARS = 500
MAX_SOURCE_TITLES = 5
RELEVANCE_SOURCE_SNIPPET_MAX_CHARS = 1600
MAX_RELEVANCE_SOURCE_CHUNKS = 10


VALIDATION_INSTRUCTIONS = """<system_role>
You are a fact-checking assistant. Validate if the answer is grounded in the provided sources.
</system_role>

<instructions>
Check:
1. Are the claims in the answer supported by the sources?
2. Are there any hallucinations or unsupported claims?
3. Is the answer accurate and complete?

Return ONLY a JSON object:
{{
    "is_grounded": true/false,
    "confidence": 0.0-1.0,
    "unsupported_claims": ["list of claims not in sources"],
    "suggestions": "how to improve the answer if needed"
}}
</instructions>
"""

RELEVANCE_CHECK_PROMPT = """<system_role>
You are a retrieval-aware relevance judge. Given the retrieved source chunks below, determine whether the answer directly addresses the user's query and is supported by those sources.
</system_role>

<instructions>
Follow this procedure:
1. Identify the main subject and intent of the user query (the specific topic, entity, mechanism, policy, or concept being asked about).
2. Check whether the answer actually answers the user's query, not merely mentions the same entity or topic.
3. Check whether the answer's main claims are grounded in the retrieved source chunks. The answer does not need to quote the chunks verbatim; a faithful summary or paraphrase is acceptable.
4. "is_relevant" is true if the answer is on-topic AND its main claims are supported by the retrieved sources. Minor details or background context not present in the source chunks do not make the answer irrelevant.

Answer "is_relevant": false only if one of these is true:
- The answer's main subject is different from the query's subject or intent.
- The answer only mentions the queried entity but does not explain or answer the requested detail.
- The answer's main factual claims are not supported by the retrieved source chunks.
- The answer says the information is "not available", "not found", "does not contain", or similar.

Return ONLY a JSON object:
{{
    "is_relevant": true/false,
    "confidence": 0.0-1.0,
    "reason": "brief explanation"
}}
</instructions>

<user_query>
User Query: {query}

Answer: {answer}

{sources_section}
</user_query>
"""


class AnswerValidator:
    """
    Agent that validates answer grounding in sources.
    
    Checks if the generated answer is factually supported by the retrieved sources.
    """
    
    def __init__(
        self,
        llm_client,
        model_name: Optional[str] = None,
        model_name_lite: Optional[str] = None,
    ):
        """
        Initialize the validator agent.
        
        Args:
            llm_client: LLMClient instance for generating text
            model_name: Model to use for validation (main model).
                None means use the client's main model.
            model_name_lite: Model to use for the relevance check.
                None means use the client's configured relevance model
                (``model_relevance``), which defaults to ``model_lite`` or
                ``model_main`` for providers without a dedicated lite model.
        """
        self.llm = llm_client
        
        # Use main model (2.5 Flash) for deep validation - requires higher accuracy.
        # None means use the client's default main model.
        self.model_name = model_name
        
        # Relevance-check model: explicit override wins, then the client's
        # configured relevance model. This stays provider-agnostic.
        self.model_name_lite = model_name_lite or getattr(llm_client, "model_relevance", None)
    
    async def validate(
        self, 
        answer: str, 
        sources: List[str],
        skip_if_short: bool = True
    ) -> Dict[str, Any]:
        """
        Validate if an answer is grounded in the provided sources.
        
        Args:
            answer: Generated answer to validate
            sources: List of source texts used to generate the answer
            skip_if_short: Skip validation for very short answers
            
        Returns:
            Dict with is_grounded, confidence, unsupported_claims, suggestions
        """
        # Skip validation for very short answers (likely simple facts)
        if skip_if_short and len(answer) < SHORT_ANSWER_CHAR_LIMIT:
            return {
                "is_grounded": True,
                "confidence": 0.8,
                "unsupported_claims": [],
                "suggestions": "",
                "skipped": True,
                "reason": "Answer too short to require validation"
            }
        
        # Skip if no sources provided
        if not sources:
            return {
                "is_grounded": False,
                "confidence": 0.3,
                "unsupported_claims": ["No sources provided"],
                "suggestions": "Answer may not be grounded without sources",
                "skipped": False,
            }
        
        try:
            # Format sources for prompt
            sources_text = "\n\n".join([
                f"Source {i+1}:\n{src[:SOURCE_SNIPPET_MAX_CHARS]}"  # Limit each source
                for i, src in enumerate(sources[:MAX_VALIDATION_SOURCES])  # Max 5 sources
            ])

            truncated_answer = answer[:ANSWER_VALIDATION_MAX_CHARS]
            base_prompt = (
                f"{VALIDATION_INSTRUCTIONS}\n\n"
                f"<user_query>\n"
                f"Sources:\n{sources_text}\n\n"
                f"Answer to validate:\n{truncated_answer}\n"
                f"</user_query>"
            )

            settings = get_settings()
            repeat_prompt = getattr(settings, "ENABLE_VALIDATOR_PROMPT_REPETITION", False)
            repeat_context_threshold = getattr(settings, "PROMPT_REPETITION_CONTEXT_THRESHOLD", None)

            prompt = base_prompt
            if repeat_prompt:
                if repeat_context_threshold is None or len(sources_text) > repeat_context_threshold:
                    prompt = f"{base_prompt}\n\n{VALIDATION_INSTRUCTIONS}"
            
            # Use async API to avoid blocking event loop
            result_text = await self.llm.generate_text(
                prompt,
                model=self.model_name,
                temperature=0.1,
                top_p=0.8,
            )
            
            result = self._parse_response(result_text)
            logger.debug(
                "Validation result: grounded=%s confidence=%s",
                result["is_grounded"],
                result["confidence"],
            )
            
            return result
            
        except Exception as e:
            # SECURITY: Fail-closed behavior - validation errors should not assume grounded
            logger.error("Validation failed: %s", e, exc_info=True)
            return {
                "is_grounded": False,  # Fail-closed: assume not grounded on error
                "confidence": 0.0,  # Zero confidence on validation failure
                "unsupported_claims": ["Validation failed - unable to verify grounding"],
                "suggestions": "Validation could not be completed. Manual review recommended.",
                "error": "Validation error occurred",  # Generic message, details in logs
            }
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the JSON response from the model.
        
        Args:
            response_text: Raw response from model
            
        Returns:
            Parsed validation result
        """
        try:
            # Clean up response
            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(text)
            
            return {
                "is_grounded": result.get("is_grounded", True),
                "confidence": float(result.get("confidence", 0.5)),
                "unsupported_claims": result.get("unsupported_claims", []),
                "suggestions": result.get("suggestions", ""),
                "skipped": False,
            }
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # SECURITY: Fail-closed - parse errors should not assume grounded
            logger.warning("Failed to parse validation response: %s", e)
            return {
                "is_grounded": False,  # Fail-closed: cannot trust unparseable response
                "confidence": 0.0,  # Zero confidence on parse failure
                "unsupported_claims": ["Unable to parse validation response"],
                "suggestions": "Validation response could not be parsed. Manual review recommended.",
                "parse_error": str(e),
            }
    
    def quick_check(self, answer: str, sources: List[str]) -> bool:
        """
        Quick local check for obvious grounding issues.
        
        Uses composite grounding metrics (keyword overlap, methodology code
        grounding, and bigram overlap) for a more robust check than simple
        word-split matching.
        
        Use this before the full LLM validation to save costs.
        
        Args:
            answer: Generated answer
            sources: Source texts
            
        Returns:
            True if answer passes quick check, False if suspicious
        """
        if not sources:
            return False

        try:
            from ..evaluation.grounding_metrics import composite_grounding_score

            citations = [{"snippet": s} for s in sources]
            metrics = composite_grounding_score(answer, citations)

            # Defensive: verify metrics shape before accessing keys.
            required_keys = {"methodology_grounding", "composite", "bigram_overlap"}
            if not isinstance(metrics, dict) or not required_keys.issubset(metrics):
                logger.warning("quick_check: unexpected metrics shape, failing closed")
                return False

            # Methodology grounding is critical: if codes are mentioned but
            # not found in sources, fail immediately regardless of composite.
            if metrics["methodology_grounding"] == 0.0 and re.search(r'\bVM\d{4}\b', answer, re.IGNORECASE):
                return False

            # Hallucinated answers often have decent keyword overlap (domain
            # jargon matches) but poor bigram overlap (phrases don't appear).
            # Require composite >= 0.4 AND bigram overlap >= 0.1 to pass.
            if metrics["composite"] < 0.4:
                return False
            if metrics["bigram_overlap"] < 0.1:
                return False

            return True

        except Exception as e:
            # SECURITY: Fail-closed — any error means we cannot trust the check.
            logger.error("quick_check failed: %s", e, exc_info=True)
            return False

    async def check_relevance(
        self,
        query: str,
        answer: str,
        source_titles: Optional[List[str]] = None,
        source_chunks: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Check if the answer is relevant to the user's query using LLM.

        This is a retrieval-aware check: the judge sees the actual retrieved
        source chunks, not just titles, so it can decide whether the answer is
        both on-topic and grounded in the sources.

        Args:
            query: Original user query
            answer: Generated answer to check
            source_titles: Optional titles of the retrieved source documents
                the answer was grounded in; gives the judge context about what
                the answer is based on.
            source_chunks: Optional list of retrieved source chunk texts.
                When provided, these are embedded in the prompt so the judge
                can verify that the answer is actually supported by the KB.

        Returns:
            Dict with is_relevant, confidence, reason
        """
        # Skip for very short answers
        if len(answer) < SHORT_RELEVANCE_ANSWER_CHAR_LIMIT:
            return {
                "is_relevant": True,
                "confidence": 0.7,
                "reason": "Answer too short to evaluate",
                "skipped": True
            }

        try:
            source_parts = []
            if source_chunks:
                chunk_text = "\n\n".join(
                    str(chunk)[:RELEVANCE_SOURCE_SNIPPET_MAX_CHARS]
                    for chunk in source_chunks[:MAX_RELEVANCE_SOURCE_CHUNKS]
                    if chunk
                )
                if chunk_text:
                    source_parts.append(
                        f"Retrieved source chunks the answer should be grounded in:\n\n{chunk_text}"
                    )

            if source_titles:
                titles = "\n".join(f"- {t[:150]}" for t in source_titles[:MAX_SOURCE_TITLES] if t)
                if titles:
                    source_parts.append(f"Source document titles:\n{titles}")

            sources_section = ""
            if source_parts:
                sources_section = "\n" + "\n\n".join(source_parts) + "\n"

            prompt = RELEVANCE_CHECK_PROMPT.format(
                query=query[:RELEVANCE_QUERY_MAX_CHARS],
                answer=answer[:ANSWER_VALIDATION_MAX_CHARS],
                sources_section=sources_section,
            )

            result_text = await self.llm.generate_text(
                prompt,
                model=self.model_name_lite,
                temperature=0.1,
                top_p=0.8,
            )

            result = self._parse_relevance_response(result_text)
            logger.info(
                "Relevance check: relevant=%s confidence=%s reason=%s",
                result["is_relevant"],
                result["confidence"],
                result.get("reason", ""),
            )

            return result

        except Exception:
            logger.error("Relevance check failed", exc_info=True)
            return {
                "is_relevant": False,
                "confidence": 0.0,
                "reason": "Relevance check failed",
                "error": "Relevance check failed"
            }
    
    def _parse_relevance_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the relevance check JSON response."""
        try:
            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(text)
            
            return {
                "is_relevant": result.get("is_relevant", True),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", ""),
                "skipped": False
            }
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Failed to parse relevance response: %s", e)
            return {
                "is_relevant": True,  # Fail-open
                "confidence": 0.5,
                "reason": "Parse error",
                "parse_error": str(e)
            }
