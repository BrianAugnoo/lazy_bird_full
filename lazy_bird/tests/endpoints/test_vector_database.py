def test_get_all_vector_databases(client, crud_database):
    from lazy_bird.models.vector_database import VectorDatabase

    with crud_database() as session:
        session.add_all([VectorDatabase(name="vector-a"), VectorDatabase(name="vector-b")])
        session.commit()

    response = client.get("/vector-databases/")

    assert response.status_code == 200
    names = {database["name"] for database in response.json()}
    assert {"vector-a", "vector-b"}.issubset(names)


def test_get_vector_database(client, crud_database):
    from lazy_bird.models.vector_database import VectorDatabase

    with crud_database() as session:
        vector_database = VectorDatabase(name="vector-a")
        session.add(vector_database)
        session.commit()
        session.refresh(vector_database)
        vector_database_id = vector_database.id

    response = client.get(f"/vector-databases/{vector_database_id}")

    assert response.status_code == 200
    assert response.json() == {"id": vector_database_id, "name": "vector-a"}


def test_get_vector_database_returns_not_found(client):
    response = client.get("/vector-databases/9999")

    assert response.status_code == 404