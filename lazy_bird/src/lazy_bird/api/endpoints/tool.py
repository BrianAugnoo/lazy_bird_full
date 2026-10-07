"""Tools and hooks: listing, settings of class modules, reloading."""

from fastapi import APIRouter

from lazy_bird.agents import hook as hooks
from lazy_bird.agents import tools
from lazy_bird.agents.callables import Entry
from lazy_bird.schemas.extension_settings import ModuleSettingsIn, ModuleSettingsOut
from lazy_bird.schemas.extensions import CallableOut

router = APIRouter()


def _out(entry: Entry) -> CallableOut:
    return CallableOut(
        id=entry.id,
        name=entry.name,
        description=entry.description,
        extension=entry.extension,
        module=entry.module,
        file_path=entry.file_path,
        class_name=entry.owner.__name__ if entry.owner else None,
        needs_settings=entry.needs_settings,
        meta_params=list(entry.meta_params),
        required_meta=list(entry.required_meta),
        accepts_any_meta=entry.accepts_any_meta,
        parameters=entry.schema.get("function", {}).get("parameters") if entry.schema else None,
    )


@router.get("/tools/", response_model=list[CallableOut], tags=["tools"])
def list_tools():
    return [_out(entry) for entry in tools.all_tools()]


@router.get("/tools/settings", response_model=list[ModuleSettingsOut], tags=["tools"])
def list_tool_settings():
    return tools.settings_store.all()


@router.get("/tools/settings/{file_path:path}", response_model=ModuleSettingsOut, tags=["tools"])
def get_tool_settings(file_path: str):
    return tools.settings_store.get(file_path)


@router.put("/tools/settings/{file_path:path}", response_model=ModuleSettingsOut, tags=["tools"])
def update_tool_settings(file_path: str, payload: ModuleSettingsIn):
    return tools.settings_store.update(file_path, payload.kwargs)


@router.post("/tools/reload", response_model=list[CallableOut], tags=["tools"])
def reload_tools():
    tools.initialize_tools()
    return list_tools()


@router.get("/hooks/", response_model=list[CallableOut], tags=["hooks"])
def list_hooks():
    return [_out(entry) for entry in hooks.all_hooks()]


@router.get("/hooks/settings", response_model=list[ModuleSettingsOut], tags=["hooks"])
def list_hook_settings():
    return hooks.settings_store.all()


@router.get("/hooks/settings/{file_path:path}", response_model=ModuleSettingsOut, tags=["hooks"])
def get_hook_settings(file_path: str):
    return hooks.settings_store.get(file_path)


@router.put("/hooks/settings/{file_path:path}", response_model=ModuleSettingsOut, tags=["hooks"])
def update_hook_settings(file_path: str, payload: ModuleSettingsIn):
    return hooks.settings_store.update(file_path, payload.kwargs)


@router.post("/hooks/reload", response_model=list[CallableOut], tags=["hooks"])
def reload_hooks():
    hooks.initialize_hooks()
    return list_hooks()
