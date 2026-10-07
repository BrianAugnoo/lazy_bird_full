"""Every route answers with a uniform payload, never a traceback, whatever it receives."""

import re

import pytest

import lazy_bird.main as main_module

SKIP = {("POST", "/extensions/reload"), ("POST", "/tools/reload"), ("POST", "/hooks/reload"), ("POST", "/models/sync"), ("POST", "/models/hub/login")}
PARAM = re.compile(r"{([^}:]+)(:path)?}")


def routes():
    for path, operations in sorted(main_module.app.openapi()["paths"].items()):
        for method in sorted(operations):
            if (method.upper(), path) not in SKIP:
                yield method.upper(), path


@pytest.mark.parametrize(("method", "path"), list(routes()))
def test_routes_never_leak_tracebacks(client, method, path, monkeypatch):
    import lazy_bird.tools.model_extraction as extraction

    monkeypatch.setattr(extraction, "download_model", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    url = PARAM.sub(lambda match: "999999" if "id" in match.group(1) else "missing", path)

    response = client.request(method, url, json={} if method in ("POST", "PUT", "PATCH") else None)

    assert response.status_code < 500 or response.json()["error"]["code"] in ("internal_error", "storage_failed", "external_service_error", "hub_unreachable", "engine_error")
    assert "Traceback" not in response.text
    if response.status_code >= 400:
        error = response.json()["error"]
        assert error["code"] and error["message"] and "details" in error
