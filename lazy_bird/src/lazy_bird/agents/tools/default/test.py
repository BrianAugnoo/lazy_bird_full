from lazy_bird.embedding import generate_query_embedding
from lazy_bird import database
import json

def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """
    Search the Lazy Bird knowledge base.

    Args:
        query: The question or information to search for.
        top_k: Maximum number of results to return.
    """
    vector, model = generate_query_embedding(query)
    rows = database.vector_retrieve(model.name, top_k, vector)
    return json.dumps([{key: value for key, value in row.items() if key != "vector" or key == "embedded_id"} for row in rows], indent=2, ensure_ascii=False)



tools = [search_knowledge_base]