import pytest

from lazy_bird.agents.hook import initialize_hooks
from lazy_bird.agents.tools import initialize_tools
from lazy_bird.crud import agent as agent_crud
from lazy_bird.crud import session as session_crud
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError
from lazy_bird.schemas.agent import AgentIn
from lazy_bird.schemas.session import SessionIn


@pytest.fixture
def registries(crud_database, fake_inference):
    initialize_tools()
    initialize_hooks()


def new_session(title: str = "work") -> int:
    return session_crud.create(SessionIn(title=title, meta={"workspace": "lazy_bird"})).id


def test_agents_reference_existing_extension_items(registries):
    session_id = new_session()

    created = agent_crud.create(AgentIn(name="a", session_id=session_id, tools=["default-knowledge_base-search_knowledge_base"], skills=["default/writing-reports"]))

    assert created.valid
    with pytest.raises(InvalidInputError) as error:
        agent_crud.create(AgentIn(name="b", session_id=session_id, tools=["search_knowledge_base"], instruction_fulls=["default/ghost"]))
    assert set(error.value.details["fields"]) == {"tools", "instruction_fulls"}


def test_one_master_per_session(registries):
    session_id = new_session()
    agent_crud.create(AgentIn(name="lead", session_id=session_id, master=True))

    with pytest.raises(ConflictError):
        agent_crud.create(AgentIn(name="second", session_id=session_id, master=True))


def test_sub_agents_stay_in_their_session_and_form_no_cycle(registries):
    session_id, other = new_session(), new_session("other")
    child = agent_crud.create(AgentIn(name="child", session_id=session_id))
    parent = agent_crud.create(AgentIn(name="parent", session_id=session_id, sub_agents_ids=[child.id]))
    stranger = agent_crud.create(AgentIn(name="stranger", session_id=other))

    assert agent_crud.get(child.id).parent_agents_ids == [parent.id]
    with pytest.raises(InvalidInputError):
        agent_crud.update(child.id, {"sub_agents_ids": [parent.id]})
    with pytest.raises(InvalidInputError):
        agent_crud.update(parent.id, {"sub_agents_ids": [stranger.id]})


def test_an_agent_preset_creates_its_sub_agents_or_reuses_them(registries):
    session_id = new_session()

    assistant = agent_crud.create_from_preset(session_id, "default/assistant")
    agents = {agent.preset: agent for agent in agent_crud.get_by_session(session_id)}
    second = agent_crud.create_from_preset(session_id, "default/assistant")

    assert set(agents) == {"default/assistant", "default/researcher"}
    assert assistant.sub_agents_ids == [agents["default/researcher"].id]
    assert second.sub_agents_ids == [agents["default/researcher"].id]
    assert agents["default/researcher"].tools == ["default-knowledge_base-search_knowledge_base"]
    assert len(agent_crud.get_by_session(session_id)) == 3


def test_a_session_preset_creates_shared_agents_and_its_master(registries):
    created = session_crud.create_from_preset("default/research-team")

    agents = agent_crud.get_by_session(created.id)
    assert created.title == "research-team"
    assert sorted(agent.preset for agent in agents) == ["default/assistant", "default/researcher"]
    assert [agent.preset for agent in agents if agent.master] == ["default/assistant"]


def test_deleting_a_session_removes_its_agents_and_links(registries):
    created = session_crud.create_from_preset("default/research-team")

    session_crud.delete(created.id)

    assert agent_crud.get_all() == []
    with pytest.raises(NotFoundError):
        session_crud.get(created.id)


def test_the_tools_seen_by_the_llm_include_skill_tools(registries):
    session_id = new_session()
    researcher = agent_crud.create_from_preset(session_id, "default/researcher")

    assert [tool.name for tool in agent_crud.tools_of(researcher.id)] == ["search_knowledge_base", "load_skill", "read_skill_file"]


def test_agents_of_an_unknown_session_are_not_found(registries):
    with pytest.raises(NotFoundError):
        agent_crud.get_by_session(404)
    with pytest.raises(NotFoundError):
        agent_crud.create_from_preset(404, "default/researcher")
