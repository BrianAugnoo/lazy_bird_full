import importlib
import importlib.util
from types import ModuleType

from lazy_bird.crud import file as file_crud
from lazy_bird.crud import llm_model as llm_model_crud
from lazy_bird.crud import selected_model_embeding as selected_model_crud


class ChunckerError(Exception):
    pass


class UnsupportedFormatError(ChunckerError):
    pass


class NoSelectedEmbeddingModelError(ChunckerError):
    pass


def _extension_module(extension: str) -> ModuleType | None:
    module_name = extension.lower().lstrip(".")
    if not module_name.isidentifier():
        return None

    import_path = f"{__name__}.extensions.{module_name}"
    if importlib.util.find_spec(import_path) is None:
        return None
    return importlib.import_module(import_path)


def _selected_context(llm_model_id: int) -> int:
    model = llm_model_crud.find(llm_model_id)
    if model is None:
        raise ChunckerError("The selected embedding model does not exist.")

    context_length = model.selected_context or model.max_context_length
    if context_length is None or context_length <= 0:
        raise ChunckerError("The selected model has no valid context length.")
    return context_length


async def chunck(file_id: int):
    file = file_crud.get(file_id)
    if file is None:
        return ChunckerError(f"File {file_id} does not exist.")

    selection = selected_model_crud.get()
    if selection.llm_model_id is None:
        return NoSelectedEmbeddingModelError("No embedding model is selected.")

    module = _extension_module(file.extension)
    if module is None:
        file_crud.update_status(file.id, "format-error")
        return UnsupportedFormatError(f"Unsupported file extension: {file.extension}")

    file_crud.update_status(file.id, "processing")
    try:
        chunk_function = getattr(module, "Chunck")
        chunks = await chunk_function(
            file=file,
            max_token=_selected_context(selection.llm_model_id),
        )
        return chunks
    except Exception as exc:
        file_crud.update_status(file.id, "chunck-error")
        return exc
