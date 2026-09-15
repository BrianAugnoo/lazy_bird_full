import asyncio
from pathlib import Path
from typing import Any

import frontmatter
import tiktoken

from lazy_bird.models.file import File


class MarkdownChunckError(Exception):
    pass


def _document_parts(markdown: str) -> tuple[dict[str, Any], str, int]:
    document = frontmatter.loads(markdown)
    lines = markdown.splitlines(keepends=True)
    body_start_line = 1

    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() in {"---", "..."}:
                body_start_line = index + 2
                break

    return dict(document.metadata), document.content, body_start_line


def _paragraphs(content: str, first_line: int):
    paragraph_lines: list[str] = []
    paragraph_start = first_line

    for line_number, line in enumerate(content.splitlines(keepends=True), start=first_line):
        if line.strip():
            if not paragraph_lines:
                paragraph_start = line_number
            paragraph_lines.append(line)
        elif paragraph_lines:
            yield "".join(paragraph_lines).rstrip("\r\n"), paragraph_start
            paragraph_lines = []

    if paragraph_lines:
        yield "".join(paragraph_lines).rstrip("\r\n"), paragraph_start


def _position(content: str, offset: int, first_line: int) -> tuple[int, int]:
    prefix = content[:offset]
    line = first_line + prefix.count("\n")
    last_newline = prefix.rfind("\n")
    row = len(prefix) if last_newline == -1 else len(prefix) - last_newline - 1
    return line, row


def _chunk_paragraph(
    paragraph: str,
    first_line: int,
    max_token: int,
    encoding,
):
    tokens = encoding.encode(paragraph)
    if not tokens:
        return

    overlap = min(50, max(1, max_token // 10)) if len(tokens) > max_token else 0
    step = max_token - overlap

    for token_start in range(0, len(tokens), step):
        token_end = min(token_start + max_token, len(tokens))
        char_start = len(encoding.decode(tokens[:token_start]))
        char_end = len(encoding.decode(tokens[:token_end]))
        content = encoding.decode(tokens[token_start:token_end])
        start_line, start_row = _position(paragraph, char_start, first_line)
        end_line, end_row = _position(paragraph, max(char_start, char_end - 1), first_line)

        yield {
            "content": content,
            "start_line": start_line,
            "end_line": end_line,
            "start_row": start_row,
            "end_row": end_row,
            "token_count": token_end - token_start,
        }

        if token_end == len(tokens):
            break


def _build_chunks(file: File, max_token: int) -> list[dict[str, Any]]:
    if max_token <= 1:
        raise ValueError("max_token must be greater than 1.")

    path = Path(file.path)
    markdown = path.read_text(encoding="utf-8")
    document_metadata, content, first_line = _document_parts(markdown)
    encoding = tiktoken.get_encoding("cl100k_base")
    chunks = []

    for paragraph_index, (paragraph, paragraph_line) in enumerate(
        _paragraphs(content, first_line),
        start=1,
    ):
        for paragraph_chunk in _chunk_paragraph(
            paragraph,
            paragraph_line,
            max_token,
            encoding,
        ):
            token_count = paragraph_chunk.pop("token_count")
            paragraph_chunk["meta_data"] = {
                **document_metadata,
                "source": str(path),
                "paragraph": paragraph_index,
                "token_count": token_count,
            }
            chunks.append(paragraph_chunk)

    return chunks


async def Chunck(file: File, max_token: int) -> list[dict[str, Any]]:
    try:
        return await asyncio.to_thread(_build_chunks, file, max_token)
    except Exception as exc:
        raise MarkdownChunckError(f"Could not chunk Markdown file {file.path}: {exc}") from exc
