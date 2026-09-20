import importlib
import pkgutil
from pathlib import Path

from lazy_bird.crud import inference_engine as engine_crud
from lazy_bird.crud import selected_inference_engine

def initialize_inference_engines():
    package = importlib.import_module("lazy_bird.inference.engines")
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        engine_crud.upsert(module.name, info.name)
        
def _inference_context():
    selected = selected_inference_engine.get()
    if selected is None:
        raise RuntimeError("No inference engine is selected")
    module = importlib.import_module(f"lazy_bird.inference.engines.{Path(selected.file_path).stem}")
    settings = module.EngineSettings.model_validate(selected.kwargs)
    return module, settings

def single_turn(query: str, instructions: str = None):
    module, settings = _inference_context()
    return module.single_turn(query, settings, instructions)