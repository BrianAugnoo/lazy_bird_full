from lazy_bird.embedding import embed_query, vector_space
from lazy_bird import database
import json
from lazy_bird.logging_config import traced

@traced
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """
    Search the Lazy Bird knowledge base.

    Args:
        query: The question or information to search for.
        top_k: Maximum number of results to return.
    """
    vector, resolved = embed_query(query)
    rows = database.vector_retrieve(vector_space(resolved), top_k, vector)
    return json.dumps([{key: value for key, value in row.items() if key != "vector" or key == "embedded_id"} for row in rows], indent=2, ensure_ascii=False)



tools = [search_knowledge_base]