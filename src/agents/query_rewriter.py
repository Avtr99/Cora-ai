"""
Query Rewriter Agent

Rewrites user queries to improve RAG retrieval:
- Fixes typos and spelling errors
- Expands acronyms (VCM, REDD+, CDM, etc.)
- Clarifies ambiguous intent
- Breaks down complex queries into sub-queries if needed
"""

import json
import logging
import re
import datetime
import html
from typing import Dict, Any, List, Optional

from ..query_processing.filter_extractor import get_allowed_filter_fields

logger = logging.getLogger(__name__)

# VCM-specific acronym expansions for context
VCM_ACRONYMS = {
    "VCM": "Voluntary Carbon Market",
    "REDD+": "Reducing Emissions from Deforestation and Forest Degradation",
    "CDM": "Clean Development Mechanism",
    "GHG": "Greenhouse Gas",
    "MRV": "Monitoring, Reporting and Verification",
    "VCS": "Verified Carbon Standard",
    "GS": "Gold Standard",
    "ICVCM": "Integrity Council for the Voluntary Carbon Market",
    "CCP": "Core Carbon Principles",
    "ARR": "Afforestation, Reforestation and Revegetation",
    "IFM": "Improved Forest Management",
    "ALM": "Agricultural Land Management",
    "AFOLU": "Agriculture, Forestry and Other Land Use",
    "tCO2e": "tonnes of CO2 equivalent",
    "ETS": "Emissions Trading System",
    "NDC": "Nationally Determined Contribution",
    "SBTi": "Science Based Targets initiative",
    "CORSIA": "Carbon Offsetting and Reduction Scheme for International Aviation",
    "FLAG": "Forest, Land and Agriculture",
    "ODS": "Ozone Depleting Substances",
    "GHGP": "Greenhouse Gas Protocol",
    "AIM": "Advanced and Indirect Mitigation",
    "TCAT": "Taskforce for Corporate Action Transparency",
}

# Acronyms that are also common English words; only expand in exact canonical form
# to avoid false positives (e.g., "aim" the verb vs "AIM" the acronym).
CASE_SENSITIVE_ONLY = {"AIM", "FLAG"}

REWRITE_PROMPT = """<system_role>
You are a domain expert query optimizer for a Voluntary Carbon Market (VCM) knowledge base.
Your goal is to transform ambiguous user inputs into precise, semantic vector search queries with strict metadata filtering.
</system_role>

<context>
    <current_date>{current_date}</current_date>
    <chat_history>
    {chat_history}
    </chat_history>
</context>

<knowledge_base>
    <common_acronyms>
        <term id="VCM">Voluntary Carbon Market</term>
        <term id="VCS">Verified Carbon Standard (Verra)</term>
        <term id="GS">Gold Standard</term>
        <term id="CCB">Climate, Community & Biodiversity Standards</term>
        <term id="REDD+">Reducing Emissions from Deforestation and Forest Degradation</term>
        <term id="CDM">Clean Development Mechanism</term>
        <term id="MRV">Monitoring, Reporting and Verification</term>
        <term id="ICVCM">Integrity Council for the Voluntary Carbon Market</term>
        <term id="VM0048/VM0007">Verra Methodology codes</term>
        <term id="ARR">Afforestation, Reforestation and Revegetation</term>
        <term id="IFM">Improved Forest Management</term>
        <term id="CCP">Core Carbon Principles</term>
        <term id="CORSIA">Carbon Offsetting and Reduction Scheme for International Aviation</term>
    </common_acronyms>
    
    <allowed_metadata_fields>
        <instruction>Only use fields listed below. Do not invent new fields.</instruction>
        <taxonomy_note>
        IMPORTANT — Correct taxonomy for metadata filtering:
        - CARBON REGISTRIES (issue credits): Verra, Gold Standard, CDM, PACM (CDM successor under Article 6.4), ART, American Carbon Registry, Climate Action Reserve, Plan Vivo, Global Carbon Council, Isometric, Puro.earth
        - STANDARDS, INITIATIVES, AND GOVERNANCE BODIES (set rules, do NOT issue credits): ICVCM, SBTi, VCMI, Social Carbon, Carbon Standards International, GHG Protocol, CCB, SD VISta, TCAT
        - POLICY FRAMEWORKS (government/UN mechanisms and compliance schemes): CORSIA, Article 6.4, VCM Policy, EU ETS, UK ETS, China ETS, California Cap-and-Trade, Washington Cap-and-Invest, RGGI, K-ETS, NZ ETS
        Use category="registry" + registry="..." for actual registries.
        Use category="standard" + standard="..." for standards bodies.
        Use category="policy" + policy_framework="..." for policy frameworks.
        </taxonomy_note>
        <fields_list>
        {allowed_fields}
        </fields_list>
    </allowed_metadata_fields>
</knowledge_base>

<instructions>
    <step_1>
        **Coreference Resolution**: Analyze the <chat_history> to identify what pronouns like "it", "he", or "that" refer to. Replace them with specific nouns in the query.
    </step_1>
    <step_2>
        **Semantic Expansion**: Fix typos and expand VCM acronyms using the <knowledge_base>. Ensure the query is optimized for vector similarity search (natural language).
    </step_2>
    <step_3>
        **Metadata Extraction**: Identify specific filtering criteria (registry, methodology, project, policy, developer).
        - Append these to the query using `field="value"` syntax.
        - STRICT RULE: You must check <allowed_metadata_fields> before applying a filter. If the field is not in the list, include the term in the natural language text only.
    </step_3>
    <step_4>
        **Sub-Query Generation**: If the user asks for multiple distinct data points, break the request into a list of specific sub-queries.
    </step_4>
</instructions>

<examples>
    <example>
        <input>currnt price of red plus credits in brazil</input>
        <output>
        {{
            "rewritten_query": "current market price of REDD+ carbon credits in Brazil",
            "sub_queries": ["latest REDD+ credit prices Brazil", "historical REDD+ price trends Brazil"],
            "detected_intent": "pricing_inquiry",
            "corrections_made": ["Fixed typo: currnt -> current", "Expanded: red plus -> REDD+"]
        }}
        </output>
    </example>
    <example>
        <input>how is VM0048 different from other deforestation methodologies</input>
        <output>
        {{
            "rewritten_query": "Verra methodology VM0048 REDD+ deforestation baseline requirements comparison with VM0007 VM0009",
            "sub_queries": ["VM0048 jurisdictional approach REDD+ GHG accounting requirements", "VM0007 VM0009 older REDD+ methodologies baseline flexibility", "Verra deforestation methodology comparison baseline assessment"],
            "detected_intent": "methodology_comparison",
            "corrections_made": ["Expanded REDD+ acronym", "Added methodology context for comparison"]
        }}
        </output>
    </example>
    <example>
        <input>what are ICVCM CCP requirements for carbon credits</input>
        <output>
        {{
            "rewritten_query": "Integrity Council Core Carbon Principles requirements carbon credit quality standards ICVCM category=\"standard\"",
            "sub_queries": ["ICVCM Core Carbon Principles ten requirements additionality permanence", "CCP carbon credit quality assessment ICVCM eligibility", "Core Carbon Principles monitoring leakage safeguards verification"],
            "detected_intent": "standard_compliance",
            "corrections_made": ["Expanded ICVCM -> Integrity Council for the Voluntary Carbon Market", "Expanded CCP -> Core Carbon Principles", "Added category filter for standard documents"]
        }}
        </output>
    </example>
    <example>
        <input>Article 6.4 mechanism rules under Paris Agreement</input>
        <output>
        {{
            "rewritten_query": "Article 6.4 mechanism implementation rules Paris Agreement UNFCCC category=\"policy\" policy_framework=\"Article 6.4\"",
            "sub_queries": ["Article 6.4 supervisory body procedures approval", "A6.4 mechanism baseline additionality requirements", "Paris Agreement Article 6 paragraph 4 implementation framework"],
            "detected_intent": "policy_inquiry",
            "corrections_made": ["Correctly classified as policy framework, not registry", "Added category and policy_framework filters"]
        }}
        </output>
    </example>
    <example>
        <input>VCS standard verification rules for IFM projects</input>
        <output>
        {{
            "rewritten_query": "Verified Carbon Standard verification rules Improved Forest Management projects VCS registry=\"VCS\"",
            "sub_queries": ["VCS Improved Forest Management methodology requirements verification", "Verra IFM project validation monitoring reporting verification MRV", "VCS standard carbon credit issuance IFM forest management"],
            "detected_intent": "standard_verification",
            "corrections_made": ["Expanded VCS -> Verified Carbon Standard", "Expanded IFM -> Improved Forest Management", "Added registry filter for VCS documents"]
        }}
        </output>
    </example>
    <example>
        <input>gold standard projects in kenya</input>
        <output>
        {{
            "rewritten_query": "Gold Standard certified carbon offset projects in Kenya registry=\"Gold Standard\"",
            "sub_queries": ["Gold Standard Kenya carbon offset project registration", "Kenya Gold Standard project validation verification", "Gold Standard Africa reforestation renewable energy projects Kenya"],
            "detected_intent": "project_search",
            "corrections_made": ["Expanded GS -> Gold Standard", "Added registry filter for Gold Standard documents"]
        }}
        </output>
    </example>
</examples>

<output_format>
Return ONLY a valid JSON object. Do not include markdown formatting (like ```json).
Structure:
{{
    "rewritten_query": "string",
    "sub_queries": ["string", "string"],
    "detected_intent": "string",
    "corrections_made": ["string"]
}}
</output_format>

<user_query>
{user_query}
</user_query>"""


class QueryRewriterAgent:
    """
    Agent that rewrites queries for improved RAG retrieval.
    
    Uses Gemini to fix typos, expand acronyms, and clarify intent.
    Designed to be lightweight and fast.
    """
    
    def __init__(self, llm_client, model_name: Optional[str] = None):
        """
        Initialize the query rewriter agent.
        
        Args:
            llm_client: LLMClient instance used to generate text
            model_name: Optional model to use for rewriting; if None the
                client's default model is used
        """
        self.llm = llm_client
        self.model_name = model_name
    
    async def rewrite(self, query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Rewrite a user query for better retrieval.
        
        Args:
            query: Original user query
            chat_history: Optional list of conversation messages for context resolution
              Each message should have 'role' ('user', 'assistant', 'system') and 'content' keys
            
        Returns:
            Dict with rewritten_query, sub_queries, detected_intent, corrections_made
        """
        if not query or not query.strip():
            return {
                "rewritten_query": query,
                "sub_queries": [],
                "detected_intent": "empty query",
                "corrections_made": []
            }
        
        try:
            allowed_fields = sorted(get_allowed_filter_fields())
            sanitized_fields = [re.sub(r"[^A-Za-z0-9_]", "_", field) for field in allowed_fields]
            sanitized_fields = [field for field in sanitized_fields if field]
            
            # Format chat history for prompt
            history_text = "No prior conversation history."
            if chat_history:
                # Take last 3 turns to save tokens while maintaining context
                recent_history = chat_history[-3:] if len(chat_history) > 3 else chat_history
                history_lines = []
                for msg in recent_history:
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    if content:
                        # Validate role against allowlist to prevent injection
                        valid_roles = {'user', 'assistant', 'system'}
                        safe_role = role if role in valid_roles else 'user'
                        history_lines.append(f"{safe_role}: {content}")
                history_text = "\n".join(history_lines) if history_lines else "No prior conversation history."
            
            # Defensive check for reserved prompt markers on raw inputs
            # All XML-style tags used in REWRITE_PROMPT (both opening and closing)
            reserved_markers = [
                "<user_query>", "</user_query>",
                "<system_role>", "</system_role>",
                "<context>", "</context>",
                "<current_date>", "</current_date>",
                "<chat_history>", "</chat_history>",
                "<knowledge_base>", "</knowledge_base>",
                "<common_acronyms>", "</common_acronyms>",
                "<term ", "</term>",
                "<allowed_metadata_fields>", "</allowed_metadata_fields>",
                "<instruction>", "</instruction>",
                "<taxonomy_note>", "</taxonomy_note>",
                "<fields_list>", "</fields_list>",
                "<instructions>", "</instructions>",
                "<step_1>", "</step_1>",
                "<step_2>", "</step_2>",
                "<step_3>", "</step_3>",
                "<step_4>", "</step_4>",
                "<examples>", "</examples>",
                "<example>", "</example>",
                "<input>", "</input>",
                "<output>", "</output>",
                "<output_format>", "</output_format>",
            ]
            query_lower = query.lower()
            history_lower = history_text.lower()
            for marker in reserved_markers:
                if marker.lower() in query_lower or marker.lower() in history_lower:
                    logger.warning("Reserved prompt marker detected in input, rejecting")
                    raise ValueError(f"Invalid input: contains reserved marker '{marker}'")
            
            # Sanitize user inputs to prevent prompt injection
            # First decode any HTML entities, then escape special characters
            sanitized_query = html.escape(html.unescape(query))
            sanitized_history = html.escape(html.unescape(history_text))
            
            prompt = REWRITE_PROMPT.format(
                current_date=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
                chat_history=sanitized_history,
                user_query=sanitized_query,
                allowed_fields=", ".join(sanitized_fields) if sanitized_fields else "(none)"
            )
            
            # Generate rewritten query via LLM client
            result_text = await self.llm.generate_text(
                prompt,
                model=self.model_name,
                temperature=0.1,
                top_p=0.8,
                json_mode=True,
            )

            # Parse JSON response
            result = self._parse_response(result_text, query)
            logger.debug(f"Query rewritten: '{query}' -> '{result['rewritten_query']}'")
            
            return result
            
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}. Using original query.")
            return {
                "rewritten_query": query,
                "sub_queries": [],
                "detected_intent": "unknown",
                "corrections_made": []
            }
    
    def _parse_response(self, response_text: str, original_query: str) -> Dict[str, Any]:
        """
        Parse the JSON response from the model.
        
        Args:
            response_text: Raw response from model
            original_query: Original query as fallback
            
        Returns:
            Parsed result dict
        """
        try:
            # Clean up response - remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```"):
                # Remove markdown code block
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            result = json.loads(text)
            
            # Validate required fields
            if "rewritten_query" not in result:
                result["rewritten_query"] = original_query
            if "sub_queries" not in result:
                result["sub_queries"] = []
            if "detected_intent" not in result:
                result["detected_intent"] = "unknown"
            if "corrections_made" not in result:
                result["corrections_made"] = []
                
            return result
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse rewrite response as JSON: {response_text[:100]}")
            return {
                "rewritten_query": original_query,
                "sub_queries": [],
                "detected_intent": "unknown",
                "corrections_made": []
            }
    
    def quick_expand_acronyms(self, query: str) -> str:
        """
        Quick local acronym expansion without LLM call.
        
        Use this for simple queries where LLM call is overkill.
        
        Args:
            query: User query
            
        Returns:
            Query with expanded acronyms
        """
        expanded = query
        for acronym, expansion in VCM_ACRONYMS.items():
            # Expand acronyms case-insensitively, except for blocklisted ones
            # that are also common English words (e.g., AIM, FLAG).
            pattern = rf'\b{re.escape(acronym)}\b'
            if re.search(pattern, expanded, re.IGNORECASE):
                def _repl(m, acr=acronym, exp=expansion):
                    matched = m.group(0)
                    if matched == acr:
                        return f"{acr} ({exp})"
                    if acr not in CASE_SENSITIVE_ONLY and matched.lower() == acr.lower():
                        return f"{matched} ({exp})"
                    return matched
                expanded = re.sub(
                    pattern,
                    _repl,
                    expanded,
                    count=1,
                    flags=re.IGNORECASE
                )
        return expanded
