from types import SimpleNamespace

import lazy_bird.crud.api_key as api_key_crud
import lazy_bird.tools.hf_auth as hf_auth


def test_authenticate_hf_does_not_login_without_key(monkeypatch):
    monkeypatch.setattr(api_key_crud, "find", lambda name: None)
    login_calls = []
    warning_calls = []
    monkeypatch.setattr(hf_auth, "login", lambda key: login_calls.append(key))
    monkeypatch.setattr(hf_auth.logger, "warning", lambda message: warning_calls.append(message))

    hf_auth.authenticate_hf()

    assert login_calls == []
    assert len(warning_calls) == 1
    assert "API key not found" in warning_calls[0]


def test_authenticate_hf_logs_in_with_saved_key(monkeypatch):
    monkeypatch.setattr(api_key_crud, "find", lambda name: SimpleNamespace(key="hf_secret"))
    login_calls = []
    monkeypatch.setattr(hf_auth, "login", lambda key: login_calls.append(key))

    hf_auth.authenticate_hf()

    assert login_calls == ["hf_secret"]


def test_authenticate_hf_logs_login_failure(monkeypatch):
    monkeypatch.setattr(api_key_crud, "find", lambda name: SimpleNamespace(key="expired"))
    error_calls = []

    def fail_login(key):
        raise RuntimeError("expired token")

    monkeypatch.setattr(hf_auth, "login", fail_login)
    monkeypatch.setattr(hf_auth.logger, "error", lambda message: error_calls.append(message))

    hf_auth.authenticate_hf()

    assert len(error_calls) == 1
    assert "expired token" in error_calls[0]
