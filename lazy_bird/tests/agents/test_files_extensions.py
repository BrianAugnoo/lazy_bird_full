import json

import pytest

from lazy_bird.agents import agent_preset, instruction, session_preset, skill
from lazy_bird.agents.agent_preset import AgentPresetData
from lazy_bird.agents.session_preset import SessionPresetData
from lazy_bird.errors import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from lazy_bird.extension.discovery import load_failures


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """Empty extension roots so tests never write into the package."""
    monkeypatch.setattr(instruction, "ROOT", tmp_path / "instruction")
    monkeypatch.setattr(skill, "ROOT", tmp_path / "skill")
    monkeypatch.setattr(agent_preset.registry, "root", tmp_path / "agent_preset")
    monkeypatch.setattr(session_preset.registry, "root", tmp_path / "session_preset")
    instruction.ensure_folders()
    skill.ensure_folders()
    agent_preset.registry.ensure_folders()
    session_preset.registry.ensure_folders()
    return tmp_path


def test_instructions_are_listed_created_and_composed(roots):
    (roots / "instruction" / "full" / "default" / "base.md").write_text("You are helpful.")
    instruction.create("sub", "short", "Be brief.")

    assert [item.id for item in instruction.instructions("full")] == ["default/base"]
    assert instruction.get("sub", "custom/short").editable
    assert instruction.compose(["default/base"], ["custom/short"], "Speak French.") == "You are helpful.\n\nBe brief.\n\nSpeak French."
    assert instruction.update("sub", "custom/short", "Be very brief.").content() == "Be very brief."
    instruction.delete("sub", "custom/short")
    assert instruction.instructions("sub") == []


def test_default_instructions_are_read_only_and_names_are_checked(roots):
    (roots / "instruction" / "full" / "default" / "base.md").write_text("x")

    with pytest.raises(ForbiddenError):
        instruction.update("full", "default/base", "changed")
    with pytest.raises(InvalidInputError):
        instruction.create("full", "../escape", "x")
    with pytest.raises(InvalidInputError):
        instruction.instructions("other")
    instruction.create("full", "mine", "x")
    with pytest.raises(ConflictError):
        instruction.create("full", "mine", "y")


def test_skills_expose_their_description_and_load_their_body_on_demand(roots):
    created = skill.create("reports", "Write reports.", "Step one.")
    (created.folder / "templates").mkdir()
    (created.folder / "templates" / "report.md").write_text("# Title")

    found = skill.find("reports")
    assert (found.id, found.description, found.files) == ("custom/reports", "Write reports.", ["templates/report.md"])
    assert found.content().strip() == "Step one."
    assert skill.read_file(found, "templates/report.md") == "# Title"
    assert "custom/reports: Write reports." in skill.listing(["custom/reports"])
    with pytest.raises(NotFoundError):
        skill.read_file(found, "../../outside.txt")


def test_skill_tools_load_skills_for_the_llm(roots):
    from lazy_bird.agents.tools.default.skills import load_skill, read_skill_file

    created = skill.create("reports", "Write reports.", "Step one.")
    (created.folder / "example.txt").write_text("example")

    assert load_skill("custom/reports").startswith("Step one.")
    assert "example.txt" in load_skill("reports")
    assert read_skill_file("reports", "example.txt") == "example"


def test_a_skill_whose_name_differs_from_its_folder_is_reported(roots):
    folder = roots / "skill" / "default" / "folder-name"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: other\ndescription: d\n---\nbody")

    assert skill.skills() == []
    assert any(failure.kind == "skill" and "folder name" in failure.error for failure in load_failures())


def preset(name: str, **values) -> dict:
    return {"name": name, **values}


def test_agent_presets_are_validated_against_their_file_name_and_references(roots):
    folder = roots / "agent_preset" / "default"
    (folder / "solo.json").write_text(json.dumps(preset("solo")))
    (folder / "renamed.json").write_text(json.dumps(preset("other")))
    (folder / "broken.json").write_text(json.dumps(preset("broken", tools=["missing-tool-x"], sub_agents=["default/ghost"], parent_agents=[])))
    (folder / "lead.json").write_text(json.dumps(preset("lead", sub_agents=["default/solo"])))

    presets = {item.id: item for item in agent_preset.registry.presets()}

    assert presets["default/solo"].valid and presets["default/lead"].valid
    assert presets["default/renamed"].errors == {"name": "must equal the file name 'renamed'"}
    assert "parent_agents" in presets["default/broken"].errors
    with pytest.raises(InvalidInputError) as error:
        agent_preset.registry.valid_data("default/renamed")
    assert error.value.code == "invalid_preset"


def test_custom_presets_can_be_written_but_not_renamed(roots):
    created = agent_preset.registry.create(AgentPresetData(name="mine", description="d"))

    assert created.id == "custom/mine" and created.editable
    with pytest.raises(InvalidInputError):
        agent_preset.registry.update("custom/mine", AgentPresetData(name="other"))
    with pytest.raises(InvalidInputError):
        agent_preset.registry.create(AgentPresetData(name="bad", sub_agents=["default/missing"]))
    agent_preset.registry.delete("custom/mine")
    assert agent_preset.registry.presets() == []


def test_session_presets_need_a_master_among_their_agents(roots):
    (roots / "agent_preset" / "default" / "solo.json").write_text(json.dumps(preset("solo")))
    (roots / "session_preset" / "default" / "team.json").write_text(json.dumps(preset("team", agents=["default/solo"], master="default/other")))

    [team] = session_preset.registry.presets()

    assert team.errors == {"master": "must be one of the session's agents"}
    assert session_preset.registry.create(SessionPresetData(name="ok", agents=["default/solo"], master="default/solo")).valid


def test_shipped_presets_are_valid(crud_database):
    from lazy_bird.agents.hook import initialize_hooks
    from lazy_bird.agents.tools import initialize_tools

    initialize_tools()
    initialize_hooks()

    assert all(item.valid for item in agent_preset.registry.presets()), [item.errors for item in agent_preset.registry.presets()]
    assert all(item.valid for item in session_preset.registry.presets())
