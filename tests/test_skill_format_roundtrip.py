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


def test_list_section_that_would_change_is_kept_verbatim():
    body = "Intro.\n\n## Steps\n\n1. First.\n\n- option a\n- option b\n\n2. Last.\n"
    assert _roundtrip(body).strip() == body.strip()


def test_plain_procedure_list_still_parses():
    parsed = parse_body("## Procedure\n\n1. first\n2. second\n")
    assert parsed["procedure"] == ["first", "second"]
    assert parsed["body_extra"] == ""


def test_known_section_after_intro_keeps_its_position():
    body = "# Title\n\nIntro.\n\n## When to Use\n\n- a bug\n\n## Steps\n\n1. First.\n2. Second.\n"
    assert _roundtrip(body).strip() == body.strip()


def test_blank_lines_are_preserved():
    body = "# Title\n## Custom\nText right under the heading.\n\n\n## Next\nMore.\n"
    assert _roundtrip(body).strip() == body.strip()


def test_odysseus_layout_still_parses_into_fields():
    body = "## When to Use\n\nWhen it breaks.\n\n## Procedure\n\n1. a\n2. b\n\n## Notes\n\nExtra.\n"
    parsed = parse_body(body)
    assert parsed["when_to_use"] == "When it breaks."
    assert parsed["procedure"] == ["a", "b"]
    assert _roundtrip(body).strip() == body.strip()
