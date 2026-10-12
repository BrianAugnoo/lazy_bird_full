import json

from lazy_bird.crud.search import search


def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """
    Search in the knowledge base.

    Args:
        query: The question or information to search for.
        top_k: Maximum number of results to return.
    """
    results = search(query, top_k)
    return json.dumps(
        [
            {
                "file": result.file_name,
                "lines": [result.chunk.start_line, result.chunk.end_line],
                "content": result.chunk.content,
                "distance": result.distance,
            }
            for result in results
        ],
        indent=2,
        ensure_ascii=False,
    )


tools = [search_knowledge_base]
