from lazy_bird.database import db
from lazy_bird.models.vector_database import VectorDatabase
from sqlmodel import select

def populate(names: list[str]):
    with db() as session:
        existing = {item.name for item in session.exec(select(VectorDatabase)).all()}
        for name in names:
            if name not in existing: session.add(VectorDatabase(name=name))
        session.commit()

def get_all():
    with db() as session: return session.exec(select(VectorDatabase)).all()
