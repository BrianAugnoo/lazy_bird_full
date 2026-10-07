import lazy_bird.crud.api_key as api_key_crud
import lazy_bird.tools.hf_auth as hf_auth
from lazy_bird.schemas.api_key import APIKeyIn


def test_without_stored_key_hugging_face_is_used_anonymously(crud_database, monkeypatch):
    calls = []
    monkeypatch.setattr("huggingface_hub.login", lambda **kwargs: calls.append(kwargs))

    assert hf_auth.authenticate_hf() is False
    assert calls == []


def test_the_stored_secret_is_used_to_log_in(crud_database, monkeypatch):
    api_key_crud.create(APIKeyIn(name="HuggingFace", key="hf_secret"))
    calls = []
    monkeypatch.setattr("huggingface_hub.login", lambda **kwargs: calls.append(kwargs))

    assert hf_auth.authenticate_hf() is True
    assert calls == [{"token": "hf_secret", "add_to_git_credential": False}]


def test_login_failures_never_raise(crud_database, monkeypatch):
    api_key_crud.create(APIKeyIn(name="HuggingFace", key="expired"))

    def fail(**kwargs):
        raise RuntimeError("expired token")

    monkeypatch.setattr("huggingface_hub.login", fail)

    assert hf_auth.authenticate_hf() is False


def test_logging_out_never_raises(monkeypatch):
    import huggingface_hub

    from lazy_bird.tools import hf_auth

    calls = []

    def logout():
        calls.append("logout")
        raise OSError("not logged in")

    monkeypatch.setattr(huggingface_hub, "logout", logout)

    hf_auth.logout_hf()

    assert calls == ["logout"]
