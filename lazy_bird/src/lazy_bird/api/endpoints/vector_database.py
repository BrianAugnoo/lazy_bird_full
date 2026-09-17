from fastapi import APIRouter, HTTPException

import lazy_bird.crud.vector_database as vector_database_crud
from lazy_bird.models.vector_database import VectorDatabase

router = APIRouter(prefix="/vector-databases", tags=["vector-databases"])


@router.get("/", response_model=list[VectorDatabase])
def get_all_vector_databases():
    return vector_database_crud.get_all()


@router.get("/{vector_database_id}", response_model=VectorDatabase)
def get_vector_database(vector_database_id: int):
    vector_database = vector_database_crud.get(vector_database_id)
    if vector_database is None:
        raise HTTPException(status_code=404, detail="Vector database not found")
    return vector_database