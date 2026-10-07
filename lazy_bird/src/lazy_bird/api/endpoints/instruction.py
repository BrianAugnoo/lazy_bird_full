from fastapi import APIRouter, Response

from lazy_bird.agents import instruction as instructions
from lazy_bird.schemas.extensions import InstructionIn, InstructionOut, InstructionUpdate

router = APIRouter(prefix="/instructions", tags=["instructions"])


def _out(item: instructions.Instruction, with_content: bool = False) -> InstructionOut:
    return InstructionOut(
        id=item.id, kind=item.kind, extension=item.extension, name=item.name, editable=item.editable,
        content=item.content() if with_content else None,
    )


@router.get("/{kind}/", response_model=list[InstructionOut])
def list_instructions(kind: str):
    """``kind`` is ``full`` (system prompts) or ``sub`` (fragments appended to them)."""
    return [_out(item) for item in instructions.instructions(kind)]


@router.post("/{kind}/", response_model=InstructionOut, status_code=201)
def create_instruction(kind: str, payload: InstructionIn):
    return _out(instructions.create(kind, payload.name, payload.content), True)


@router.get("/{kind}/{extension}/{name}", response_model=InstructionOut)
def get_instruction(kind: str, extension: str, name: str):
    return _out(instructions.get(kind, f"{extension}/{name}"), True)


@router.put("/{kind}/{extension}/{name}", response_model=InstructionOut)
def update_instruction(kind: str, extension: str, name: str, payload: InstructionUpdate):
    return _out(instructions.update(kind, f"{extension}/{name}", payload.content), True)


@router.delete("/{kind}/{extension}/{name}", status_code=204)
def delete_instruction(kind: str, extension: str, name: str):
    instructions.delete(kind, f"{extension}/{name}")
    return Response(status_code=204)
