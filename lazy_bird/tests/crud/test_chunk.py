import pytest

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.errors import NotFoundError
from lazy_bird.models.file import File


def create_file(crud_database, name: str = "notes") -> int:
    with crud_database() as session:
        file = File(name=name, path=f"/tmp/{name}.md", extension=".md", size=1)
        session.add(file)
        session.commit()
        return file.id


CHUNKS = [
    {"content": "first", "start_line": 1, "end_line": 2, "token_count": 1, "meta": {"paragraph": 1}},
    {"content": "second", "start_line": 4, "end_line": 4, "start_row": 0, "end_row": 5},
]


def test_replace_stores_chunks_in_order(crud_database):
    file_id = create_file(crud_database)

    stored = chunk_crud.replace(file_id, CHUNKS)

    assert [(chunk.position, chunk.content) for chunk in stored] == [(0, "first"), (1, "second")]
    assert stored[0].meta == {"paragraph": 1} and stored[1].meta == {}
    assert chunk_crud.for_file(file_id) == stored
    assert chunk_crud.counts([file_id, 999]) == {file_id: 2, 999: 0}


def test_replacing_chunks_drops_the_vectors_of_the_old_ones(crud_database):
    file_id = create_file(crud_database)
    old = chunk_crud.replace(file_id, CHUNKS)
    database.vector_create("org/model", [{"chunk_id": chunk.id, "vector": [1.0, 0.0]} for chunk in old])

    new = chunk_crud.replace(file_id, CHUNKS[:1])

    assert database.vector_count("org/model") == 0
    assert [chunk.content for chunk in new] == ["first"]


def test_delete_for_file_keeps_other_files_untouched(crud_database):
    first, second = create_file(crud_database, "a"), create_file(crud_database, "b")
    kept = chunk_crud.replace(second, CHUNKS)
    chunk_crud.replace(first, CHUNKS)
    database.vector_create("org/model", [{"chunk_id": chunk.id, "vector": [1.0, 0.0]} for chunk in kept])

    assert chunk_crud.delete_for_file(first) == 2
    assert chunk_crud.for_file(first) == []
    assert len(chunk_crud.for_file(second)) == 2
    assert database.vector_count("org/model") == 2


def test_unknown_chunk_is_not_found(crud_database):
    with pytest.raises(NotFoundError):
        chunk_crud.get(404)
