"""Skill URL importer — GitHub path parsing."""
import ipaddress

import pytest

from services.memory.skill_importer import (
    ResolvedSource,
    SkillImportError,
    _assert_github_url,
    _fetch_bytes,
    _list_github_dir,
    parse_skill_source,
)


def _allow_fetch(monkeypatch):
    monkeypatch.setattr(
        "services.memory.skill_importer._resolve_and_check_url",
        lambda url: [ipaddress.ip_address("93.184.216.34")],
    )


def test_parse_github_blob_skill_md():
    src = parse_skill_source(
        "https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md"
    )
    assert src.owner == "anthropics"
    assert src.repo == "skills"
    assert src.ref == "main"
    assert src.path.endswith("skills/pdf/SKILL.md")


def test_parse_github_tree_directory():
    src = parse_skill_source(
        "https://github.com/example/my-skills/tree/develop/caveman-skill"
    )
    assert src.owner == "example"
    assert src.repo == "my-skills"
    assert src.ref == "develop"
    assert src.path == "caveman-skill"


def test_parse_raw_github():
    src = parse_skill_source(
        "https://raw.githubusercontent.com/o/r/main/path/SKILL.md"
    )
    assert src.owner == "o"
    assert src.repo == "r"
    assert src.ref == "main"
    assert src.path == "path/SKILL.md"


def test_rejects_non_github():
    with pytest.raises(SkillImportError):
        parse_skill_source("https://example.com/skill.md")


def test_fetch_bytes_rejects_cross_host_redirect(monkeypatch):
    class _Resp:
        url = "https://evil.example/secret"
        status_code = 200
        content = b"x"

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr("services.memory.skill_importer.httpx.Client", _Client)
    _allow_fetch(monkeypatch)
    with pytest.raises(SkillImportError, match="redirect target"):
        _fetch_bytes("https://raw.githubusercontent.com/o/r/main/SKILL.md")


def test_assert_github_url_allows_api_host():
    _assert_github_url(
        "https://api.github.com/repos/o/r/contents?ref=main",
        context="redirect target",
    )


def test_list_github_dir_accepts_api_github_response(monkeypatch):
    monkeypatch.setattr(
        "services.memory.skill_importer._fetch_text",
        lambda url: "# skill\n",
    )
    _allow_fetch(monkeypatch)

    class _Resp:
        url = "https://api.github.com/repos/o/r/contents?ref=main"
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{
                "name": "SKILL.md",
                "type": "file",
                "download_url": "https://raw.githubusercontent.com/o/r/main/SKILL.md",
            }]

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr("services.memory.skill_importer.httpx.Client", _Client)

    out = {}
    src = ResolvedSource(owner="o", repo="r", ref="main", path="")
    _list_github_dir(src, "", out)
    assert "SKILL.md" in out


def _mock_httpx_client(monkeypatch, response):
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return response

    monkeypatch.setattr("services.memory.skill_importer.httpx.Client", _Client)
    _allow_fetch(monkeypatch)


def test_list_github_dir_surfaces_rate_limit(monkeypatch):
    class _Resp:
        url = "https://api.github.com/repos/o/r/contents?ref=main"
        status_code = 403

        def json(self):
            return {"message": "API rate limit exceeded for 203.0.113.1"}

    _mock_httpx_client(monkeypatch, _Resp())
    src = ResolvedSource(owner="o", repo="r", ref="main", path="")
    with pytest.raises(SkillImportError, match="rate limit"):
        _list_github_dir(src, "", {})


def test_fetch_bytes_surfaces_github_error_detail(monkeypatch):
    class _Resp:
        url = "https://raw.githubusercontent.com/o/r/main/SKILL.md"
        status_code = 403
        content = b""

        def json(self):
            return {"message": "Forbidden"}

    _mock_httpx_client(monkeypatch, _Resp())
    with pytest.raises(SkillImportError, match="GitHub request failed \\(403\\): Forbidden"):
        _fetch_bytes("https://raw.githubusercontent.com/o/r/main/SKILL.md")


def test_import_bundle_places_files_beside_skill_md(tmp_path):
    from services.memory.skills import SkillsManager

    files = {
        "skills/engineering/tdd/SKILL.md": "---\nname: tdd\ndescription: d\n---\n\nSee [tests.md](tests.md).\n",
        "skills/engineering/tdd/tests.md": "tests",
        "skills/engineering/tdd/agents/openai.yaml": "x: 1",
    }
    entry = SkillsManager(str(tmp_path)).import_bundle_from_files(files, owner="u")
    skill_dir = tmp_path / "skills" / "imported" / entry["name"]
    found = sorted(p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.is_file())
    assert found == ["SKILL.md", "agents/openai.yaml", "tests.md"]


def test_bundle_keeps_node_module_config_files():
    from services.memory.skill_importer import _is_text_file

    assert _is_text_file("dependency-cruiser.config.cjs")
    assert _is_text_file("eslint.config.mjs")


def test_import_bundle_leaves_out_nested_skills(tmp_path):
    from services.memory.skills import SkillsManager

    files = {
        "SKILL.md": "---\nname: parent\ndescription: d\n---\n\nBody.\n",
        "helpers/notes.md": "notes",
        "skills/child/SKILL.md": "---\nname: child\ndescription: d\n---\n\nChild.\n",
        "skills/child/ref.md": "ref",
    }
    sm = SkillsManager(str(tmp_path))
    sm.import_bundle_from_files(files, owner="u")
    assert [s["name"] for s in sm.load_all()] == ["parent"]
    skill_dir = tmp_path / "skills" / "imported" / "parent"
    found = sorted(p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.is_file())
    assert found == ["SKILL.md", "helpers/notes.md"]
