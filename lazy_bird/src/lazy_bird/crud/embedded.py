from lazy_bird.database import db
from lazy_bird.models.embedded import Embedded, EmbeddedVectorDatabase
from lazy_bird.models.vector_database import VectorDatabase
from sqlmodel import select

def create(file_id: int, llm_model_id: int, vector_database_name: str):
    with db() as session:
        vector_db = session.exec(select(VectorDatabase).where(VectorDatabase.name == vector_database_name)).first()
        if vector_db is None:
            vector_db = VectorDatabase(name=vector_database_name); session.add(vector_db); session.flush()
        embedded = session.exec(select(Embedded).where(Embedded.file_id == file_id, Embedded.llm_model_id == llm_model_id)).first()
        if embedded is None:
            embedded = Embedded(file_id=file_id, llm_model_id=llm_model_id); session.add(embedded); session.flush()
        else:
            embedded.status = "pending"
        link = session.exec(select(EmbeddedVectorDatabase).where(EmbeddedVectorDatabase.embedded_id == embedded.id, EmbeddedVectorDatabase.vector_database_id == vector_db.id)).first()
        if link is None: session.add(EmbeddedVectorDatabase(embedded_id=embedded.id, vector_database_id=vector_db.id))
        session.commit(); session.refresh(embedded); return embedded

def update_status(embedded_id: int, status: str):
    with db() as session:
        embedded = session.get(Embedded, embedded_id)
        if embedded is None: return False
        embedded.status = status; session.commit(); return True

def get(embedded_id: int):
    with db() as session: return session.get(Embedded, embedded_id)
