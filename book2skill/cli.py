from __future__ import annotations

import argparse
from pathlib import Path

from .core.compiler import build_skill_package, write_json, write_skill_markdown
from .core.extractor import extract_title
from .core.ingestion import read_text_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile a document into a Book2Skill package.")
    parser.add_argument("--input", required=True, help="Path to a source file (.txt, .md, .pdf, .docx)")
    parser.add_argument("--output", required=True, help="Output directory for generated artifacts")
    parser.add_argument("--max-items", type=int, default=10, help="Maximum number of items per category")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output)

    try:
        text = read_text_file(input_path)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc

    title = extract_title(text)
    package = build_skill_package(title=title, text=text, max_items=args.max_items)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_skill_markdown(output_dir / "SKILL.md", package)
    write_json(output_dir / "knowledge.json", package)

    print(f"Created skill package for: {title}")
    print(f"Output directory: {output_dir}")
    return 0
