from fastapi import APIRouter, Response
from lazy_bird import database, preferences
from lazy_bird.crud import file_processing
from lazy_bird.schemas.database import DatabaseDisconnectIn, DatabaseSelectionIn, SelectedDatabaseOut, VectorTableOut

router = APIRouter(prefix="/databases", tags=["databases"])

@router.get("/")
def list_databases():
    return {
        "available": database.adapter_catalog(),
        "selected_sql": database.current_config().selected_sql_database,
        "selected_vector": database.current_config().selected_vector_database,
    }


@router.get("/selected_db", response_model=SelectedDatabaseOut)
def get_selected_database():
    return {
        "sql": database.current_config().selected_sql_database,
        "vector": database.current_config().selected_vector_database,
    }

@router.put("/select")
def select_database(payload: DatabaseSelectionIn):
    """Connect to another database; switching vector database outdates the embeddings."""
    selected = database.switch_database(payload.kind, payload.name, payload.settings)
    if payload.kind == "vector":
        file_processing.outdate_processor("embedding", f"The vector database changed to {payload.name}.")
        file_processing.ensure_all(automatic=preferences.auto_embedding_enabled())
    return selected

@router.put("/disconnect")
def disconnect_database(payload: DatabaseDisconnectIn):
    return database.disconnect_database(payload.kind, payload.name, payload.drop)


@router.get("/vector/tables", response_model=list[VectorTableOut])
def list_vector_tables():
    """Model tables of the selected vector database, with their number of vectors."""
    return [VectorTableOut(model_name=name, vectors=database.vector_count(name)) for name in database.vector_tables()]


@router.delete("/vector/tables/{model_name:path}", status_code=204)
def drop_vector_table(model_name: str):
    """Delete every vector of a model; files lose their embedding with it.

    With automatic processing on, files are embedded again when the model is the
    one of the default embedding preset.
    """
    database.vector_drop(model_name)
    file_processing.forget_target("embedding", model_name)
    if preferences.auto_embedding_enabled():
        file_processing.ensure_all()
    return Response(status_code=204)
