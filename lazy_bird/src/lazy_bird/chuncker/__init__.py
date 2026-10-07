"""Split a file into chunks with the chunker of its extension.

Chunker extensions live in ``chuncker/extensions/{extension}.py`` (``md.py`` for
``.md`` files) and define ``async def Chunck(file, max_token) -> list[dict]``. Each
chunk dict has ``content``, ``start_line``, ``end_line`` and optionally
``start_row``, ``end_row``, ``token_count`` and ``meta`` (a JSON object).
"""

import importlib
import importlib.util
from types import ModuleType

from lazy_bird.crud import file as file_crud
from lazy_bird.errors import AppError, NotFoundError
from lazy_bird.preferences import chunking_max_tokens


class ChunckerError(AppError):
    status_code = 500
    code = "chunking_failed"


class UnsupportedFormatError(AppError):
    status_code = 422
    code = "unsupported_format"


def _extension_module(extension: str) -> ModuleType | None:
    module_name = extension.lower().lstrip(".")
    if not module_name.isidentifier():
        return None

    import_path = f"{__name__}.extensions.{module_name}"
    if importlib.util.find_spec(import_path) is None:
        return None
    return importlib.import_module(import_path)


def supported_extensions() -> list[str]:
    import pkgutil

    from lazy_bird.chuncker import extensions

    return sorted(f".{info.name}" for info in pkgutil.iter_modules(extensions.__path__) if not info.name.startswith("_"))


async def chunck(file_id: int) -> list[dict]:
    """Return the chunks of a file; raise ``UnsupportedFormatError`` or ``ChunckerError``."""
    file = file_crud.get(file_id)
    if file is None:
        raise NotFoundError("File", file_id)
    module = _extension_module(file.extension)
    if module is None:
        raise UnsupportedFormatError(
            f"No chunker for '{file.extension}' files (supported: {', '.join(supported_extensions())}).",
            details={"extension": file.extension},
        )
    try:
        return await module.Chunck(file=file, max_token=chunking_max_tokens())
    except AppError:
        raise
    except Exception as error:
        raise ChunckerError(f"Could not chunk {file.name}{file.extension}: {error}") from error
