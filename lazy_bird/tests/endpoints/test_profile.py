def _user(client, name):
    response = client.post("/users/", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _active(client):
    return client.get("/profile/").json()["user_id"]


def test_there_is_no_profile_user_before_any_user_exists(client):
    response = client.get("/profile/")

    assert response.status_code == 200
    assert response.json() == {"user_id": None, "user": None}


def test_the_first_user_added_becomes_the_profile_user(client):
    ada = _user(client, "Ada")
    _user(client, "Bob")

    profile = client.get("/profile/").json()

    assert profile["user_id"] == ada["id"]
    assert profile["user"] == ada


def test_another_user_can_be_chosen(client):
    _user(client, "Ada")
    bob = _user(client, "Bob")

    switched = client.put("/profile/", json={"user_id": bob["id"]})

    assert switched.status_code == 200, switched.text
    assert switched.json()["user"]["name"] == "Bob"
    assert _active(client) == bob["id"]


def test_the_profile_shows_the_current_state_of_its_user(client):
    ada = _user(client, "Ada")
    client.patch(f"/users/{ada['id']}", json={"profession": "Engineer"})

    assert client.get("/profile/").json()["user"]["profession"] == "Engineer"


def test_an_unknown_user_cannot_be_chosen(client):
    ada = _user(client, "Ada")

    response = client.put("/profile/", json={"user_id": 99})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
    assert _active(client) == ada["id"]


def test_deleting_the_profile_user_passes_the_profile_to_the_first_remaining_user(client):
    ada = _user(client, "Ada")
    bob = _user(client, "Bob")
    cleo = _user(client, "Cleo")
    client.put("/profile/", json={"user_id": cleo["id"]})

    assert client.delete(f"/users/{cleo['id']}").status_code == 204
    assert _active(client) == ada["id"]
    assert client.delete(f"/users/{ada['id']}").status_code == 204
    assert _active(client) == bob["id"]


def test_deleting_another_user_keeps_the_profile_user(client):
    ada = _user(client, "Ada")
    bob = _user(client, "Bob")

    client.delete(f"/users/{bob['id']}")

    assert _active(client) == ada["id"]


def test_without_users_the_profile_is_empty_and_the_next_user_added_takes_it(client):
    ada = _user(client, "Ada")
    client.delete(f"/users/{ada['id']}")

    assert client.get("/profile/").json() == {"user_id": None, "user": None}
    bob = _user(client, "Bob")
    assert _active(client) == bob["id"]


def test_the_database_holds_a_single_profile(client):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from lazy_bird.database import db
    from lazy_bird.models.profile import Profile

    ada = _user(client, "Ada")
    bob = _user(client, "Bob")

    with db() as session:
        session.add(Profile(id=2, user_id=bob["id"]))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    assert _active(client) == ada["id"]
