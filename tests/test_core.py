from pathlib import Path

from book2skill.core.compiler import build_skill_package, write_skill_markdown
from book2skill.core.ingestion import read_text_file
from book2skill.core.extractor import extract_title


def test_extract_title_from_markdown_heading():
    text = "# Deep Work\n\nThis is a book about focus."
    assert extract_title(text) == "Deep Work"


def test_read_txt_file_returns_text():
    path = Path("sample.txt")
    path.write_text("Knowledge is power.", encoding="utf-8")
    try:
        assert read_text_file(path) == "Knowledge is power."
    finally:
        path.unlink(missing_ok=True)


def test_build_skill_package_has_expected_sections():
    package = build_skill_package(
        title="Focus System",
        text="AI agents use context and memory. Principle: keep actions focused. Method: plan then execute.",
    )

    assert package["title"] == "Focus System"
    assert "concepts" in package
    assert "principles" in package
    assert "methods" in package
    assert package["raw_excerpt"]


def test_write_skill_markdown_creates_markdown_output(tmp_path):
    output = tmp_path / "SKILL.md"
    package = {
        "title": "Demo Skill",
        "concepts": ["Concept A"],
        "principles": ["Principle A"],
        "methods": ["Method A"],
        "raw_excerpt": "Demo excerpt",
    }

    write_skill_markdown(output, package)
    content = output.read_text(encoding="utf-8")

    assert "# Skill: Demo Skill" in content
    assert "Concept A" in content
    assert "Principle A" in content
    assert "Method A" in content
