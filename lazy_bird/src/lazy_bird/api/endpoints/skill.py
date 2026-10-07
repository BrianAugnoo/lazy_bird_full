from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from lazy_bird.agents import skill as skills
from lazy_bird.schemas.extensions import SkillIn, SkillOut, SkillUpdate

router = APIRouter(prefix="/skills", tags=["skills"])


def _out(skill: skills.Skill, with_content: bool = False) -> SkillOut:
    return SkillOut(
        id=skill.id,
        extension=skill.extension,
        name=skill.name,
        description=skill.description,
        files=skill.files,
        editable=skill.editable,
        content=skill.content() if with_content else None,
    )


@router.get("/", response_model=list[SkillOut])
def list_skills():
    return [_out(skill) for skill in skills.skills()]


@router.post("/", response_model=SkillOut, status_code=201)
def create_skill(payload: SkillIn):
    return _out(skills.create(payload.name, payload.description, payload.content), True)


@router.get("/{extension}/{name}", response_model=SkillOut)
def get_skill(extension: str, name: str):
    return _out(skills.get(f"{extension}/{name}"), True)


@router.put("/{extension}/{name}", response_model=SkillOut)
def update_skill(extension: str, name: str, payload: SkillUpdate):
    return _out(skills.update(f"{extension}/{name}", payload.description, payload.content), True)


@router.delete("/{extension}/{name}", status_code=204)
def delete_skill(extension: str, name: str):
    skills.delete(f"{extension}/{name}")
    return Response(status_code=204)


@router.get("/{extension}/{name}/files/{path:path}", response_class=PlainTextResponse)
def read_skill_file(extension: str, name: str, path: str):
    return skills.read_file(skills.get(f"{extension}/{name}"), path)
