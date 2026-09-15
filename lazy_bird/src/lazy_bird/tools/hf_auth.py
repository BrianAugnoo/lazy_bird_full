from huggingface_hub import login
import logging

logger = logging.getLogger(__name__)


def authenticate_hf():
    from lazy_bird.crud.api_key import find as find_api_key

    api_key = find_api_key("HuggingFace")
    if api_key is None:
        logger.warning("Hugging Face API key not found. Please set it up.")
    else:
        try:
            login(api_key.key)
            logger.info("Successfully authenticated with Hugging Face.")
        except Exception as e:
            logger.error(f"Failed to authenticate with Hugging Face: {e}, api_key may be invalid or expired. Please check your API key.")