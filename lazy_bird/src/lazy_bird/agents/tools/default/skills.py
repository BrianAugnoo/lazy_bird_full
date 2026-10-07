"""Built-in tools giving agents access to their skills (see ``agents/skill``)."""

from lazy_bird.agents import skill as skills


def load_skill(skill: str) -> str:
    """
    Load the full instructions of a skill listed in your system prompt.

    Args:
        skill: The skill id shown in the list of your skills, e.g. "default/pdf-reports".
    """
    found = skills.find(skill)
    resources = "\n".join(f"- {name}" for name in found.files)
    suffix = f"\n\nResource files (read them with read_skill_file):\n{resources}" if resources else ""
    return found.content().strip() + suffix


def read_skill_file(skill: str, path: str) -> str:
    """
    Read a resource file of a skill (examples, references, templates).

    Args:
        skill: The skill id, e.g. "default/pdf-reports".
        path: The file path inside the skill folder, as listed by load_skill.
    """
    return skills.read_file(skills.find(skill), path)


tools = [load_skill, read_skill_file]
