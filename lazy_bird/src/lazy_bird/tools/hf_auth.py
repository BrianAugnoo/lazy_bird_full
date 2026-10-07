"""Hugging Face authentication with the API key stored under the name ``HuggingFace``."""

from loguru import logger

HUGGING_FACE_KEY = "HuggingFace"


def authenticate_hf() -> bool:
    """Log in with the stored key; return whether it succeeded (never raises)."""
    from huggingface_hub import login

    from lazy_bird.crud.api_key import find_key

    key = find_key(HUGGING_FACE_KEY)
    if not key:
        logger.info("No '{}' API key stored: Hugging Face is used anonymously.", HUGGING_FACE_KEY)
        return False
    try:
        login(token=key, add_to_git_credential=False)
    except Exception as error:
        logger.warning("Hugging Face login failed ({}); check the '{}' API key.", error, HUGGING_FACE_KEY)
        return False
    logger.info("Logged in to Hugging Face.")
    return True


def logout_hf() -> None:
    """Forget the Hugging Face token (when its key is deleted); never raises."""
    from huggingface_hub import logout

    try:
        logout()
    except Exception as error:  # Not logged in, or the token file is already gone.
        logger.info("Hugging Face logout skipped: {}", error)


def hub_status() -> dict:
    """Who lazy_bird is logged in as on Hugging Face (``user`` is None when anonymous)."""
    from huggingface_hub import whoami

    try:
        return {"authenticated": True, "user": whoami().get("name"), "error": None}
    except Exception as error:
        return {"authenticated": False, "user": None, "error": str(error)}
