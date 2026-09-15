import importlib
import pkgutil

from fastapi import APIRouter

from . import endpoints

router = APIRouter()

for module_info in pkgutil.iter_modules(endpoints.__path__):
    module = importlib.import_module(f"{endpoints.__name__}.{module_info.name}")
    if not hasattr(module, "router"):
        raise ImportError(f"Endpoint module '{module.__name__}' has no 'router' attribute")
    router.include_router(module.router)
