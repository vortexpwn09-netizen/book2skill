from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .extractor import extract_knowledge, extract_title
from .validation import validate_knowledge_package


def build_skill_package(
    title: str,
    text: str,
    max_items: int = 10,
) -> dict[str, Any]:
    resolved_title = title or extract_title(text)
    extracted = extract_knowledge(text, max_items=max_items)
    package = {
        "title": resolved_title,
        "concepts": extracted["concepts"],
        "principles": extracted["principles"],
        "methods": extracted["methods"],
        "raw_excerpt": text[:800],
    }
    validation = validate_knowledge_package(package)
    package["validation"] = validation
    return package


def write_json(output_path: str | Path, package: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")


def write_skill_markdown(output_path: str | Path, package: dict[str, Any]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(render_skill_markdown(package), encoding="utf-8")


def render_skill_markdown(package: dict[str, Any]) -> str:

    lines = [
        f"# Skill: {package['title']}",
        "",
        "## Concepts",
    ]

    if package.get("concepts"):
        for index, concept in enumerate(package["concepts"], start=1):
            lines.append(f"{index}. {concept}")
    else:
        lines.append("*No concepts extracted*")

    lines.extend(["", "## Principles"])
    if package.get("principles"):
        for index, principle in enumerate(package["principles"], start=1):
            lines.append(f"{index}. {principle}")
    else:
        lines.append("*No principles extracted*")

    lines.extend(["", "## Methods"])
    if package.get("methods"):
        for index, method in enumerate(package["methods"], start=1):
            lines.append(f"{index}. {method}")
    else:
        lines.append("*No methods extracted*")

    lines.extend(["", "## Metadata", f"- Source: {package['title']}"])
    return "\n".join(lines) + "\n"
