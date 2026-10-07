from lazy_bird.agents import tools
from lazy_bird.agents.callables import Entry


def entry(extension: str, module: str, name: str) -> Entry:
    return Entry(id=f"{extension}-{module}-{name}", name=name, extension=extension, module=module, file_path=f"{extension}/{module}.py", function=lambda: None)


def test_default_tools_are_discovered(crud_database):
    tools.initialize_tools()

    ids = {item.id for item in tools.all_tools()}
    assert {"default-knowledge_base-search_knowledge_base", "default-skills-load_skill", "default-smtp-Smtp-send_email"} <= ids
    smtp = tools.get("default-smtp-Smtp-send_email")
    assert smtp.needs_settings and "self" not in smtp.schema["function"]["parameters"]["properties"]


def test_the_default_tool_keeps_its_name_and_others_get_their_id(monkeypatch):
    found = {item.id: item for item in (entry("acme", "web", "search"), entry("default", "kb", "search"), entry("zeta", "web", "search"), entry("acme", "web", "fetch"))}
    monkeypatch.setattr(tools._found, "entries", found)

    names = tools.llm_names(["acme-web-search", "default-kb-search", "zeta-web-search", "acme-web-fetch"])

    assert names == {"acme-web-search": "acme-web-search", "default-kb-search": "search", "zeta-web-search": "zeta-web-search", "acme-web-fetch": "fetch"}


def test_without_default_tool_the_first_one_keeps_the_name(monkeypatch):
    found = {item.id: item for item in (entry("acme", "web", "search"), entry("zeta", "web", "search"))}
    monkeypatch.setattr(tools._found, "entries", found)

    assert tools.llm_names(["zeta-web-search", "acme-web-search"]) == {"zeta-web-search": "search", "acme-web-search": "acme-web-search"}


def test_the_llm_schema_uses_the_exposed_name():
    item = Entry(id="acme-web-search", name="search", extension="acme", module="web", file_path="acme/web.py", function=lambda: None, schema={"type": "function", "function": {"name": "search", "description": "d"}})

    assert tools.llm_schema(item, "acme-web-search") == {"type": "function", "function": {"name": "acme-web-search", "description": "d"}}


def test_tool_settings_are_validated_and_saved(crud_database):
    tools.initialize_tools()

    initial = tools.settings_store.get("default/smtp.py")
    assert not initial.valid and "smtp_server" in initial.errors
    assert initial.kwargs_key["smtp_password"]["content"] == "default.basic.password"

    saved = tools.settings_store.update(
        "default/smtp.py",
        {"smtp_server": "smtp.local", "smtp_port": "465", "smtp_username": "me", "smtp_password": "secret", "sender_email": "me@local"},
    )
    assert saved.valid and saved.kwargs["smtp_port"] == 465
