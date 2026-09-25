from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship
from torch import TYPE_CHECKING

if TYPE_CHECKING:
    from lazy_bird.models.conversation import Conversation