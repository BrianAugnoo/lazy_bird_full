"""Outputs and inputs of extension items: tools, hooks, skills, instructions, presets."""

from typing import Any

from pydantic import BaseModel, Field


class CallableOut(BaseModel):
    """A tool or hook. ``needs_settings``: configure it in /tools|hooks/settings;
    ``required_meta``: session meta keys its class needs."""

    id: str
    name: str
    description: str
    extension: str
    module: str
    file_path: str
    class_name: str | None = None
    needs_settings: bool = False
    meta_params: list[str] = Field(default_factory=list)
    required_meta: list[str] = Field(default_factory=list)
    accepts_any_meta: bool = False
    parameters: dict[str, Any] | None = None


class LoadFailureOut(BaseModel):
    kind: str
    source: str
    error: str


class SkillOut(BaseModel):
    id: str
    extension: str
    name: str
    description: str
    files: list[str]
    editable: bool
    content: str | None = None


class SkillIn(BaseModel):
    name: str
    description: str = Field(min_length=1)
    content: str = ""


class SkillUpdate(BaseModel):
    description: str = Field(min_length=1)
    content: str = ""


class InstructionOut(BaseModel):
    id: str
    kind: str
    extension: str
    name: str
    editable: bool
    content: str | None = None


class InstructionIn(BaseModel):
    name: str
    content: str = ""


class InstructionUpdate(BaseModel):
    content: str


class PresetOut(BaseModel):
    """An agent or session preset; ``errors`` explains why it is invalid."""

    id: str
    extension: str
    name: str
    editable: bool
    valid: bool
    errors: dict[str, str] = Field(default_factory=dict)
    data: dict[str, Any] | None = None
