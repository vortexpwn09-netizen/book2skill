from __future__ import annotations

import re


def extract_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "Untitled Knowledge Source"

    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
        if line.startswith("## "):
            return line[3:].strip()

    first_line = lines[0]
    if len(first_line) <= 100 and not first_line.endswith("."):
        return first_line

    return "Untitled Knowledge Source"


def normalize_text_for_extraction(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        cleaned_lines.append(stripped)
    return " ".join(cleaned_lines)


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text_for_extraction(text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip() and len(sentence.strip()) > 10]


def _iter_keyword_matches(sentences: list[str], keywords: set[str]) -> list[str]:
    matches: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords):
            matches.append(sentence)
    return matches


def extract_knowledge(text: str, max_items: int = 10) -> dict[str, list[str]]:
    sentences = split_sentences(text)
    if not sentences:
        return {"concepts": [], "principles": [], "methods": []}

    concepts_keywords = {
        "agent",
        "system",
        "architecture",
        "design",
        "workflow",
        "pattern",
        "context",
        "model",
        "framework",
        "knowledge",
        "memory",
        "strategy",
    }
    principles_keywords = {
        "principle",
        "important",
        "must",
        "should",
        "best",
        "essential",
        "key",
        "guideline",
        "rule",
        "clear",
        "focus",
        "simple",
        "critical",
    }
    methods_keywords = {
        "method",
        "process",
        "workflow",
        "steps",
        "first",
        "then",
        "finally",
        "approach",
        "procedure",
        "pattern",
        "pipeline",
        "sequence",
    }

    concepts = _iter_keyword_matches(sentences, concepts_keywords)[:max_items]
    principles = _iter_keyword_matches(sentences, principles_keywords)[:max_items]
    methods = _iter_keyword_matches(sentences, methods_keywords)[:max_items]

    if not concepts:
        concepts = sentences[:max_items]
    if not principles:
        principles = sentences[:max_items]
    if not methods:
        methods = sentences[:max_items]

    return {
        "concepts": concepts[:max_items],
        "principles": principles[:max_items],
        "methods": methods[:max_items],
    }
