from fastapi import APIRouter, HTTPException
from lazy_bird.agents.tools import tools

router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("/", response_model=list[dict])
async def list_tools():
    return [{"type": t["type"],"function": t["function"], "package": t["package"], "module": t["module"]} for t in tools]