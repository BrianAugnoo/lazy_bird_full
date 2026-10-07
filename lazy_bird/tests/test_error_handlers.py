from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from lazy_bird.api.error_handlers import install_error_handlers
from lazy_bird.errors import ConflictError


class Payload(BaseModel):
    count: int


def build_client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail")

    @app.get("/conflict")
    def conflict():
        raise ConflictError("Already there.", code="already_there", details={"id": 1})

    @app.post("/payload")
    def payload(body: Payload):
        return body

    return TestClient(app, raise_server_exceptions=False)


def test_unexpected_errors_never_expose_a_traceback():
    response = build_client().get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text


def test_app_errors_keep_their_status_code_and_details():
    response = build_client().get("/conflict")

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "already_there", "message": "Already there.", "details": {"id": 1}}}


def test_request_validation_errors_are_reported_per_field():
    response = build_client().post("/payload", json={"count": "many"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "count" in response.json()["error"]["details"]["fields"]


def test_unknown_routes_use_the_uniform_format():
    response = build_client().get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
