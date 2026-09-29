"""SKILL.md body parse → emit must not lose headings or rich section content."""
from services.memory.skill_format import emit_body, parse_body


def _roundtrip(body: str) -> str:
    return emit_body(parse_body(body))


def test_unknown_headings_are_kept_in_order():
    body = "Intro.\n\n## Main flow\n\nFirst.\n\n## Standalone\n\nSecond.\n"
    assert _roundtrip(body).strip() == body.strip()


def test_rich_steps_section_is_kept_verbatim():
    body = (
        "## Steps\n\n"
        "### 1. Install\n\n"
        "Run this:\n\n"
        "```bash\nnpm i -D husky\n```\n\n"
        "- nested detail\n"
    )
    out = _roundtrip(body)
    assert "### 1. Install" in out
    assert "```bash\nnpm i -D husky\n```" in out
    assert out.strip() == body.strip()


def test_heading_inside_code_fence_is_not_a_section():
    body = "Template:\n\n```markdown\n## Destination\n\n<text>\n```\n"
    assert _roundtrip(body).strip() == body.strip()


def test_plain_procedure_list_still_parses():
    parsed = parse_body("## Procedure\n\n1. first\n2. second\n")
    assert parsed["procedure"] == ["first", "second"]
    assert parsed["body_extra"] == ""
