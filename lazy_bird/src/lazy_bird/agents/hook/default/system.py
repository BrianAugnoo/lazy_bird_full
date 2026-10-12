"""Context the LLM gets on every turn: the date, this machine and the user it works for.

Message texts are never changed: the data is attached to ``hooks["system"]`` of the
messages (see ``agents/hook/__init__.py``), the date to the user's prompt, the
environment and the user to the system prompt.
"""

import platform
from datetime import datetime
from typing import Any

import lazy_bird.crud.conversation as conversation_crud
import lazy_bird.crud.message as message_crud
from lazy_bird.crud.profile import get as get_profile
from lazy_bird.schemas.message import MessageOut

KEY = "system"
HARNESS = "Lazy Bird (development stage)"


class System:
    def __init__(self, conversation_id: int, workspace: str | None = None):
        last = message_crud.last(conversation_id)
        # Hooks also run between tool calls: the date belongs to the prompt that started the turn.
        self.prompt = last if last is not None and last.role == "user" else None
        self.instructions = conversation_crud.get_instructions(conversation_id)
        self.workspace = workspace

    def date(self):
        """Give the user's prompt the current date and time."""
        if self.prompt:
            _attach(self.prompt, "Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def environment_information(self):
        """Give the system prompt the operating system, the harness and the session's workspace."""
        if self.instructions:
            _attach(self.instructions, "Environment Information", {"OS": _os_info(), "Harness": HARNESS, "Workspace": self.workspace})

    def user_information(self):
        """Give the system prompt who the user is: the active user of the Users page."""
        if self.instructions:
            user = get_profile().user
            about = None if user is None else {
                "Name": user.name,
                "Profession": user.profession,
                "Email": user.email,
                "Age": user.age,
                "Languages": ", ".join(user.languages) or None,
                "Description": user.description,
            }
            _attach(self.instructions, "User Information", about)


def _attach(message: MessageOut, key: str, value: Any) -> None:
    """Set ``hooks["system"][key]`` of ``message`` (no write when it already holds ``value``)."""
    section = message.hooks.setdefault(KEY, {})
    if section.get(key) == value:
        return
    section[key] = value
    message_crud.edit_hooks(message.id, {KEY: section})


def _os_info() -> dict[str, str | None]:
    """What the operating system says about itself (``None`` when it does not say)."""
    system = platform.system()
    info = {"system": system, "version": platform.version()}
    if system == "Darwin":
        info["os_version"] = platform.mac_ver()[0] or None
    elif system == "Windows":
        release, version, service_pack, _ = platform.win32_ver()
        info.update(os_version=version or None, windows_release=release or None, service_pack=service_pack or None)
    elif system == "Linux":
        try:
            distro = platform.freedesktop_os_release()
        except OSError:
            distro = {}
        info.update(distribution=distro.get("PRETTY_NAME"), distribution_id=distro.get("ID"), os_version=distro.get("VERSION_ID"))
    return info


hooks = [System]
