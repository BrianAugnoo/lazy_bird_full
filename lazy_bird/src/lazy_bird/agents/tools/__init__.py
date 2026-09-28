from pathlib import Path
import importlib
import pkgutil
from transformers.utils import get_json_schema

tools = []
base_dir = Path(__file__).resolve().parent


def initialize_tools():
    global tools
    tools.clear()
    validation = {"success": [], "failed": []}
    for entry in base_dir.iterdir():
        if entry.is_dir() and not entry.name.startswith("_"):
            module_name = f"lazy_bird.agents.tools.{entry.name}"
            package = importlib.import_module(module_name)
            
            for file in pkgutil.iter_modules(package.__path__):
                if file.name.startswith("_"):
                    continue
                module = importlib.import_module(f"{module_name}.{file.name}")
                for tool in module.tools:
                    try:
                        parsed_tool = get_json_schema(tool)
                        parsed_tool["callable"] = tool
                        parsed_tool["package"] = entry.name
                        parsed_tool["module"] = file.name
                        tools.append(parsed_tool)
                        success = {
                            "name": tool.__name__,
                            "package": entry.name,
                            "module": file.name
                        }
                        validation["success"].append(success)
                    except Exception as e:
                        error = {
                            "name": tool.__name__,
                            "package": entry.name,
                            "module": file.name,
                            "error": str(e)
                        }
                        validation["failed"].append(error)                       
    return validation

def get_tools(tools_names: list[str] = None) -> list[dict]:
    return [t for t in tools if t["function"]["name"] in tools_names]