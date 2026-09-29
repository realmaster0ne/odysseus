"""`disable-model-invocation: true` makes a skill user-invoked only."""
import asyncio
import json

from services.memory.skill_format import Skill
from services.memory.skills import SkillsManager


def _md(name, *, user_only):
    flag = "disable-model-invocation: true\n" if user_only else ""
    return (
        f"---\nname: {name}\ndescription: deploy the app to production\n{flag}"
        f"status: published\nconfidence: 0.9\nowner: u\n---\n\nDeploy it.\n"
    )


def _manager(tmp_path):
    for name, user_only in (("auto-deploy", False), ("manual-deploy", True)):
        d = tmp_path / "skills" / "general" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(_md(name, user_only=user_only))
    return SkillsManager(str(tmp_path))


def test_flag_survives_parse_and_save():
    sk = Skill.from_markdown(_md("manual-deploy", user_only=True))
    assert sk.disable_model_invocation is True
    assert "disable-model-invocation: true" in sk.to_markdown()
    assert "disable-model-invocation" not in Skill.from_markdown(_md("x", user_only=False)).to_markdown()


def test_index_hides_user_only_skills_unless_asked(tmp_path):
    sm = _manager(tmp_path)
    assert [s["name"] for s in sm.index_for(owner="u")] == ["auto-deploy"]
    assert [s["name"] for s in sm.index_for(owner="u", include_user_only=True)] == ["auto-deploy", "manual-deploy"]


def test_relevance_search_hides_user_only_skills_unless_asked(tmp_path):
    sm = _manager(tmp_path)
    skills = sm.load(owner="u")
    assert [s["name"] for s in sm.get_relevant_skills("deploy the app", skills)] == ["auto-deploy"]
    names = {s["name"] for s in sm.get_relevant_skills("deploy the app", skills, include_user_only=True)}
    assert names == {"auto-deploy", "manual-deploy"}


def test_manage_skills_tool_search_and_list(tmp_path, monkeypatch):
    _manager(tmp_path)
    monkeypatch.setattr("src.constants.DATA_DIR", str(tmp_path))
    from src.tools.system import do_manage_skills

    search = asyncio.run(do_manage_skills(json.dumps({"action": "search", "query": "deploy the app"}), owner="u"))
    assert "manual-deploy" not in search["results"]
    listing = asyncio.run(do_manage_skills(json.dumps({"action": "list"}), owner="u"))["results"]
    assert "manual-deploy" in listing.split("User-invoked only")[1]
    assert "manual-deploy" not in listing.split("User-invoked only")[0]
