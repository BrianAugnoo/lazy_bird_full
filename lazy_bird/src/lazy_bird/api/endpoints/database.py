from fastapi import APIRouter, HTTPException, Response
from lazy_bird import database
from lazy_bird.schemas.database import DatabaseDisconnectIn, DatabaseSelectionIn, SelectedDatabaseOut, VectorTableOut

router = APIRouter(prefix="/databases", tags=["databases"])

@router.get("/")
def list_databases():
    return {
        "available": database.adapter_catalog(),
        "selected_sql": database.config.selected_sql_database,
        "selected_vector": database.config.selected_vector_database,
    }


@router.get("/selected_db", response_model=SelectedDatabaseOut)
def get_selected_database():
    return {
        "sql": database.config.selected_sql_database,
        "vector": database.config.selected_vector_database,
    }

@router.put("/select")
def select_database(payload: DatabaseSelectionIn):
    try:
        return database.switch_database(payload.kind, payload.name, payload.settings)
    except (ValueError, KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.put("/disconnect")
def disconnect_database(payload: DatabaseDisconnectIn):
    try:
        return database.disconnect_database(payload.kind, payload.name, payload.drop)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/vector/tables", response_model=list[VectorTableOut])
def list_vector_tables():
    """Model tables of the selected vector database, with their number of vectors."""
    return [VectorTableOut(model_name=name, vectors=database.vector_count(name)) for name in database.vector_tables()]


@router.delete("/vector/tables/{model_name:path}", status_code=204)
def drop_vector_table(model_name: str):
    database.vector_drop(model_name)
    return Response(status_code=204)
