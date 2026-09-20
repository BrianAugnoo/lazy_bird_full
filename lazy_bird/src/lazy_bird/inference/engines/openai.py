from pydantic import BaseModel, ConfigDict
from openai import OpenAI
from lazy_bird.schemas.inference_engine import Response
from lazy_bird.crud.api_key import find_key

name = "openai-client"

class EngineSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key_name: str | None = None
    base_url: str
    model_name: str
    
def validate_kwargs(kwargs):
    try:
        EngineSettings.model_validate(kwargs)
        return True
    except Exception as exc:
        return sorted({str(error.get("loc", ["unknown"])[0]) for error in exc.errors()})
    
def single_turn(query: str, settings: EngineSettings, instructions: str=None, tools: list[dict]=None):
    invalid = validate_kwargs(settings)
    if invalid is not True:
        raise ValueError(f"Invalid inference engine kwargs: {invalid}")

    settings = EngineSettings.model_validate(settings)
    api_key = "no-key"
    if settings.api_key_name:
        api_key = find_key(settings.api_key_name)
        if not api_key:
            raise RuntimeError(
                f"No API key found for '{settings.api_key_name}'"
            )

    client = OpenAI(
        base_url=settings.base_url,
        api_key=api_key,
    )
    
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {"role": "user", "content": query},
            {"role": "system", "content": instructions if instructions else ""},
        ],
        tools=tools or [],
    )
    return Response(
        content=response.choices[0].message.content,
        reasoning=response.choices[0].message.reasoning if hasattr(response.choices[0].message, "reasoning") else None,
    )