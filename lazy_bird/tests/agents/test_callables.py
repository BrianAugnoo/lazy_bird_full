import sys
import textwrap
import uuid

import pytest
from pydantic import BaseModel

from lazy_bird.agents import hook
from lazy_bird.agents.callables import MissingMetaError, NotConfiguredError, Runner, build_entries
from lazy_bird.agents.tools import _describe as describe_tool
from lazy_bird.extension import ExtensionContractError


def search(query: str, limit: int = 3) -> str:
    """
    Search something.

    Args:
        query: What to look for.
        limit: How many results.
    """
    return f"{query}:{limit}"


class Mailer:
    """Sends mail."""

    def __init__(self, settings, workspace: str, region: str = "eu"):
        self.settings, self.workspace, self.region = settings, workspace, region

    def send(self, to: str) -> str:
        """
        Send a mail.

        Args:
            to: Recipient.
        """
        return f"{self.settings.host}:{self.workspace}:{self.region}:{to}"

    def _private(self) -> None:
        """Not a tool."""


class Flexible:
    def __init__(self, **meta):
        self.meta = meta

    def show(self) -> str:
        """Show the meta."""
        return ",".join(sorted(self.meta))


class Settings(BaseModel):
    host: str


def entries(item):
    return build_entries(item, extension="ext", module="mod", file_path="ext/mod.py", describe=describe_tool)


def test_functions_become_one_entry_with_their_schema():
    [entry] = entries(search)

    assert (entry.id, entry.name, entry.is_method) == ("ext-mod-search", "search", False)
    assert entry.schema["function"]["parameters"]["required"] == ["query"]


def test_public_methods_become_entries_without_self():
    [entry] = entries(Mailer)

    assert entry.id == "ext-mod-Mailer-send"
    assert "self" not in entry.schema["function"]["parameters"]["properties"]
    assert (entry.needs_settings, entry.meta_params, entry.required_meta) == (True, ("workspace", "region"), ("workspace",))


def test_runner_builds_each_class_once_with_settings_and_meta():
    [entry] = entries(Mailer)
    runner = Runner({"workspace": "lazy_bird", "unrelated": 1}, lambda file_path: Settings(host="smtp.local"))

    assert runner.call(entry, {"to": "a@b.c"}) == "smtp.local:lazy_bird:eu:a@b.c"
    assert runner.instance(entry) is runner.instance(entry)


def test_classes_accepting_kwargs_receive_the_whole_meta():
    [entry] = entries(Flexible)

    assert Runner({"a": 1, "b": 2}, lambda path: None).call(entry) == "a,b"


def test_missing_meta_and_settings_are_explained():
    [entry] = entries(Mailer)

    with pytest.raises(MissingMetaError):
        Runner({}, lambda path: Settings(host="x")).call(entry, {"to": "a"})

    def unconfigured(path):
        raise NotConfiguredError("not configured")

    with pytest.raises(NotConfiguredError):
        Runner({"workspace": "w"}, unconfigured).call(entry, {"to": "a"})


@pytest.mark.parametrize("item", [42, staticmethod(search)])
def test_other_items_are_rejected(item):
    with pytest.raises(ExtensionContractError):
        entries(item)


def test_ids_must_stay_valid_llm_names():
    def tool_with_a_really_long_function_name_that_never_seems_to_end(x: int) -> int:
        """
        Long.

        Args:
            x: A number.
        """
        return x

    with pytest.raises(ExtensionContractError):
        build_entries(tool_with_a_really_long_function_name_that_never_seems_to_end, extension="extension", module="module", file_path="e/m.py", describe=describe_tool)


MODULES = {
    "good": '''
        from pydantic import BaseModel
        class HookSettings(BaseModel):
            prefix: str = ">"
        CALLS = []
        def log(conversation_id):
            """Log the conversation.

            Every turn."""
            CALLS.append(("log", conversation_id))
        class Guard:
            def __init__(self, conversation_id, settings, workspace=None):
                self.conversation_id, self.settings, self.workspace = conversation_id, settings, workspace
            def check(self):
                """Check the conversation."""
                CALLS.append((self.settings.prefix, self.conversation_id, self.workspace))
            def again(self):
                CALLS.append(("again", self))
        hooks = [log, Guard]
    ''',
    "bad_signature": '''
        def hook(conversation_id, extra):
            pass
        hooks = [hook]
    ''',
    "class_without_conversation": '''
        class Late:
            def check(self, conversation_id):
                pass
        hooks = [Late]
    ''',
    "method_with_argument": '''
        class Talkative:
            def __init__(self, conversation_id):
                pass
            def check(self, conversation_id):
                pass
        hooks = [Talkative]
    ''',
    "settings_without_model": '''
        class Needy:
            def __init__(self, conversation_id, settings):
                pass
            def run(self):
                pass
        hooks = [Needy]
    ''',
    "no_list": '''
        def hook(conversation_id):
            pass
    ''',
}


@pytest.fixture
def hook_package(tmp_path, monkeypatch):
    package = f"fake_hooks_{uuid.uuid4().hex}"
    extension = tmp_path / package / "acme"
    extension.mkdir(parents=True)
    (tmp_path / package / "__init__.py").write_text("")
    for name, source in MODULES.items():
        (extension / f"{name}.py").write_text(textwrap.dedent(source))
    monkeypatch.syspath_prepend(str(tmp_path))
    yield package
    for name in [name for name in sys.modules if name.startswith(package)]:
        del sys.modules[name]


def test_hook_discovery_validates_signatures_and_settings(hook_package):
    found = hook.discover_hooks(hook_package)

    assert sorted(found.entries) == ["acme-good-Guard-again", "acme-good-Guard-check", "acme-good-log"]
    assert list(found.settings) == ["acme/good.py"]
    failures = {failure.source: failure.error for failure in found.failures}
    assert set(failures) == {"acme/bad_signature.py", "acme/class_without_conversation.py", "acme/method_with_argument.py", "acme/settings_without_model.py", "acme/no_list.py"}
    assert "conversation_id" in failures["acme/bad_signature.py"]
    assert "Late.__init__ must take 'conversation_id'" in failures["acme/class_without_conversation.py"]
    assert "must take no argument" in failures["acme/method_with_argument.py"]


def test_hook_classes_read_session_values_but_not_the_conversation_id(hook_package):
    guard = hook.discover_hooks(hook_package).entries["acme-good-Guard-check"]

    assert guard.meta_params == ("workspace",) and guard.required_meta == ()


def test_hook_descriptions_are_their_whole_docstrings(hook_package):
    found = hook.discover_hooks(hook_package)

    assert found.entries["acme-good-log"].description == "Log the conversation.\n\nEvery turn."
    assert found.entries["acme-good-Guard-check"].description == "Check the conversation."
    assert found.entries["acme-good-Guard-again"].description == ""


def test_hooks_run_in_order_classes_built_with_the_conversation_id(hook_package, monkeypatch):
    monkeypatch.setattr(hook, "_found", hook.discover_hooks(hook_package))
    monkeypatch.setattr(hook.settings_store, "saved", lambda path: {"prefix": "!"})
    calls = sys.modules[f"{hook_package}.acme.good"].CALLS

    hook.run_hooks(["acme-good-log", "acme-good-Guard-check", "acme-good-Guard-again", "acme-good-Guard-again"], 7, {"workspace": "w", "conversation_id": 99})
    hook.run_hooks(["acme-good-Guard-again"], 8, {})

    assert calls[:2] == [("log", 7), ("!", 7, "w")]
    instances = [instance for name, instance in calls[2:]]
    assert instances[0] is instances[1] and instances[2] is not instances[0]  # one instance per pass, shared by its methods
