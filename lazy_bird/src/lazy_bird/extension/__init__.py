"""Shared machinery for dynamically discovered extension modules.

lazy_bird discovers engines, tools, hooks, skills, instructions and presets by
convention instead of manual wiring. This package holds what those discoveries
have in common:

- ``discovery``: walking packages and ``{extension_name}/`` folders, checking
  required attributes, and recording load failures;
- ``settings``: the ``*Settings`` + ``fields`` + ``kwargs_key`` contract used by
  every configurable extension.
"""


class ExtensionContractError(Exception):
    """An extension module does not respect the contract of its discovery point."""
