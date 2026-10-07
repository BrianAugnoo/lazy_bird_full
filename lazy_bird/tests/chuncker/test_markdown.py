from pathlib import Path

import pytest

from lazy_bird.chuncker.extensions.md import Chunck, MarkdownChunckError
from lazy_bird.models.file import File


@pytest.mark.anyio
async def test_markdown_chunks_paragraphs_and_preserves_metadata(tmp_path: Path):
    path = tmp_path / "notes.md"
    path.write_text(
        "---\ntitle: Notes\n---\nFirst paragraph.\n\nSecond paragraph.\n",
        encoding="utf-8",
    )
    file = File(name="notes", path=str(path), extension=".md", size=path.stat().st_size)

    chunks = await Chunck(file=file, max_token=100)

    assert [chunk["content"] for chunk in chunks] == ["First paragraph.", "Second paragraph."]
    assert [(chunk["start_line"], chunk["end_line"]) for chunk in chunks] == [(4, 4), (6, 6)]
    assert chunks[0]["meta"]["title"] == "Notes"
    assert chunks[0]["meta"]["paragraph"] == 1


@pytest.mark.anyio
async def test_markdown_splits_large_paragraph_with_overlap(tmp_path: Path):
    path = tmp_path / "large.md"
    path.write_text(" ".join(f"word{index}" for index in range(100)), encoding="utf-8")
    file = File(name="large", path=str(path), extension=".md", size=path.stat().st_size)

    chunks = await Chunck(file=file, max_token=20)

    assert len(chunks) > 1
    assert all(chunk["token_count"] <= 20 for chunk in chunks)
    assert all(chunk["start_line"] == 1 and chunk["end_line"] == 1 for chunk in chunks)
    assert chunks[0]["content"][-5:] in chunks[1]["content"]


@pytest.mark.anyio
async def test_markdown_returns_domain_error_for_unreadable_file(tmp_path: Path):
    file = File(name="missing", path=str(tmp_path / "missing.md"), extension=".md", size=0)

    with pytest.raises(MarkdownChunckError, match="Could not chunk Markdown file"):
        await Chunck(file=file, max_token=20)
