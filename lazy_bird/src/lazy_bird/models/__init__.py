import importlib
import pkgutil
from pathlib import Path


current_file = Path(__file__).stem

for module_info in pkgutil.iter_modules([str(Path(__file__).parent)]):
	module_name = module_info.name
	if module_name.startswith("_") or module_name == current_file:
		continue

	importlib.import_module(f"{__package__}.{module_name}")
