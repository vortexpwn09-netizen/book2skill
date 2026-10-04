from __future__ import annotations


def validate_knowledge_package(package: dict) -> dict:
    title = package.get("title", "").strip()
    concepts = package.get("concepts", []) or []
    principles = package.get("principles", []) or []
    methods = package.get("methods", []) or []

    errors: list[str] = []
    if not title:
        errors.append("Missing title")
    if not concepts:
        errors.append("No concepts extracted")
    if not principles:
        errors.append("No principles extracted")
    if not methods:
        errors.append("No methods extracted")

    return {
        "valid": not errors,
        "errors": errors,
        "title": title,
        "concept_count": len(concepts),
        "principle_count": len(principles),
        "method_count": len(methods),
    }
