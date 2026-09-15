import re
from pathlib import Path


def chunk_markdown_by_title(file_path: str, max_token: int = None) -> list[dict]:
    """
    Chunck un fichier Markdown par titre (titre + son contenu).
    
    Args:
        file_path: Chemin vers le fichier Markdown
        max_token: Optionnel, non utilisé (pour compatibilité)
        
    Returns:
        Liste de chunks avec {file_name, file_path, content}
    """
    path = Path(file_path)
    markdown = path.read_text(encoding="utf-8")
    
    # Parser les sections par titre
    title_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    sections = []
    last_pos = 0
    
    for match in title_pattern.finditer(markdown):
        # Ajouter contenu avant le titre à la section précédente
        if sections and match.start() > last_pos:
            sections[-1]['content'] += markdown[last_pos:match.start()]
        elif not sections and match.start() > 0:
            # Contenu avant le premier titre
            before = markdown[:match.start()].strip()
            if before:
                sections.append({
                    'title': 'Introduction',
                    'content': before + '\n'
                })
        
        # Créer nouvelle section avec titre
        sections.append({
            'title': match.group(2),
            'content': match.group(0) + '\n'
        })
        last_pos = match.end()
    
    # Ajouter le reste du contenu au dernier titre
    if sections and last_pos < len(markdown):
        sections[-1]['content'] += markdown[last_pos:]
    elif not sections:
        sections.append({'title': 'Content', 'content': markdown})
    
    # Formater résultats
    chunks = []
    for section in sections:
        if section['content'].strip():
            chunks.append({
                'file_name': path.name,
                'file_path': str(path),
                'content': section['content'].strip()
            })
    
    return chunks