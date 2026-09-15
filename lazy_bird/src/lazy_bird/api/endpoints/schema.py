from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from pathlib import Path

from lazy_bird.tools.db_schema import get_schema_diagram


router = APIRouter(tags=["schema"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")


@router.get("/shemas", include_in_schema=False)
def show_database_schema(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="shemas.html",
        context={"diagram": get_schema_diagram()},
    )
