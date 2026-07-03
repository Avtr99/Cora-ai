"""Heuristic conversational query classifier."""

from __future__ import annotations

import re

_WORD_COUNT_RE = re.compile(r"\b\w+\b")
_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9\s]")
_MULTISPACE_RE = re.compile(r"\s+")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")
_ELONGATED_CONVERSATIONAL_RE = re.compile(r"(h+i+|he+y+|he+l+o+|yo+|su+p+|ok+|th+x+|by+e+)")
_GREETING_PREFIX_RE = re.compile(
    r"^(hi|hello|hey|howdy|hiya|good\s+(?:morning|afternoon|evening|day))\s*[,!.]*\s*"
)
_SELF_INTRO_RE = re.compile(
    r"(?:my name is|i am|i m|im|this is|call me)\s+\S+(?:\s+\S+){0,3}"
)
_GREETING_FOLLOWUP_RE = re.compile(
    r"(?:there|everyone|team|all|cora|assistant|friend|folks"
    r"|my name is|i am|i m|im|this is|call me)(?:\s+\S+){0,3}"
)
_GREETING_FOLLOWUP_PREFIX_RE = re.compile(
    r"^(there|everyone|team|all|cora|assistant|friend|folks)\s+"
)
_EXACT_CONVERSATIONAL = frozenset({
    "hi there",
    "hi there how are you",
    "hi there how are you doing",
    "hey there",
    "hello there", "hello", "hey", "hola", "bonjour", "greetings", "howdy", "hiya",
    "good morning", "good afternoon", "good evening", "good day",
    "how are you", "how are you doing", "how is it going",
    "whats up", "what s up", "sup", "yo",
    "thanks", "thank you", "thanks a lot", "thank you so much",
    "thanks for the help", "thanks for your help", "thx", "ty",
    "ok", "okay", "got it", "understood", "noted",
    "sounds good", "no worries", "all good", "cool", "great", "nice",
    "bye", "goodbye", "see you", "see you later", "later", "cheers",
    "take care", "have a good day", "have a nice day",
    "test", "testing", "asdf",
    "what can you do", "who are you", "what are you",
    "what is your name", "are you a bot", "are you an ai",
    "help", "help me", "how can you help", "how can you help me",
    "tell me about yourself", "introduce yourself",
    "can you hear me", "are you there",
})


def is_conversational_query(query: str, long_query_word_limit: int = 20) -> bool:
    if not query:
        return False

    query_word_count = len(_WORD_COUNT_RE.findall(query))
    if query_word_count > long_query_word_limit:
        return False

    compact_query = _NON_ALNUM_SPACE_RE.sub(" ", query.lower().strip())
    compact_query = _MULTISPACE_RE.sub(" ", compact_query).strip()
    compact_query = _REPEATED_CHAR_RE.sub(r"\1\1", compact_query)

    if compact_query in _EXACT_CONVERSATIONAL:
        return True

    if _ELONGATED_CONVERSATIONAL_RE.fullmatch(compact_query):
        return True

    greeting_prefix = _GREETING_PREFIX_RE.match(compact_query)
    if greeting_prefix:
        remainder = compact_query[greeting_prefix.end() :].strip()
        if not remainder:
            return True
        if remainder in _EXACT_CONVERSATIONAL:
            return True
        if _GREETING_FOLLOWUP_RE.fullmatch(remainder):
            return True
        if _SELF_INTRO_RE.fullmatch(remainder):
            return True

        followup_match = _GREETING_FOLLOWUP_PREFIX_RE.match(remainder)
        if followup_match:
            after_followup = remainder[followup_match.end() :].strip()
            if after_followup in _EXACT_CONVERSATIONAL:
                return True

    if _SELF_INTRO_RE.fullmatch(compact_query):
        return True

    return False
