import importlib
import importlib.util
from types import ModuleType

from lazy_bird.crud import file as file_crud
from lazy_bird.preferences import chunking_max_tokens


class ChunckerError(Exception):
    pass


class UnsupportedFormatError(ChunckerError):
    pass


def _extension_module(extension: str) -> ModuleType | None:
    module_name = extension.lower().lstrip(".")
    if not module_name.isidentifier():
        return None

    import_path = f"{__name__}.extensions.{module_name}"
    if importlib.util.find_spec(import_path) is None:
        return None
    return importlib.import_module(import_path)


async def chunck(file_id: int):
    file = file_crud.get(file_id)
    if file is None:
        return ChunckerError(f"File {file_id} does not exist.")

    module = _extension_module(file.extension)
    if module is None:
        file_crud.update_status(file.id, "format-error")
        return UnsupportedFormatError(f"Unsupported file extension: {file.extension}")

    file_crud.update_status(file.id, "processing")
    try:
        chunk_function = getattr(module, "Chunck")
        return await chunk_function(file=file, max_token=chunking_max_tokens())
    except Exception as exc:
        file_crud.update_status(file.id, "chunck-error")
        return exc
