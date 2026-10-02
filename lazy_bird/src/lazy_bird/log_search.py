from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from rank_bm25 import BM25Okapi

from lazy_bird.log_parser import LogEntry, iter_log_entries


class LogSearchError(ValueError):
    """Raised when a log search request is invalid."""


def tokenize_log(text: str, *, ignore_case: bool = True) -> list[str]:
    """Tokenize names such as ``functionCall`` and dotted log locations."""
    camel = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    tokens = re.findall(r"[A-Za-z0-9]+", camel)
    return [token.lower() for token in tokens] if ignore_case else tokens


def _normalized_date(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def _in_range(entry: LogEntry, since: datetime | None, until: datetime | None) -> bool:
    if entry.timestamp is None:
        return False
    timestamp = entry.timestamp
    normalized_since = _normalized_date(since)
    normalized_until = _normalized_date(until)
    return (normalized_since is None or timestamp >= normalized_since) and (normalized_until is None or timestamp <= normalized_until)


def search_logs(
    query: str | None = None,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    last_n: int | None = None,
    mode: Literal["bm25", "regex"] = "bm25",
    ignore_case: bool = True,
    log_file: Path = Path("logs.txt"),
) -> list[LogEntry]:
    """Search log entries and return matches chronologically."""
    if not query and since is None:
        raise LogSearchError("Une requête ou --since est obligatoire quand aucun filtre n'est fourni.")
    if last_n is not None and last_n < 0:
        raise LogSearchError("last_n doit être supérieur ou égal à zéro.")
    if mode not in ("bm25", "regex"):
        raise LogSearchError(f"Mode de recherche inconnu: {mode}")

    candidates = [entry for entry in iter_log_entries(log_file) if _in_range(entry, since, until)]
    if not query:
        matches = candidates
    elif mode == "regex":
        try:
            pattern = re.compile(query, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            raise LogSearchError(f"Expression régulière invalide: {exc}") from exc
        matches = [entry for entry in candidates if pattern.search(entry.raw_text)]
    else:
        tokens = tokenize_log(query)
        if not tokens:
            matches = []
        else:
            corpus = [tokenize_log(entry.raw_text, ignore_case=ignore_case) or ["__empty__"] for entry in candidates]
            scores = BM25Okapi(corpus).get_scores(tokenize_log(query, ignore_case=ignore_case))
            matches = []
            for entry, score in zip(candidates, scores):
                if score > 0:
                    entry.score = float(score)
                    matches.append(entry)

    matches.sort(key=lambda entry: entry.start_line)
    if last_n is not None:
        matches = matches[-last_n:] if last_n else []
    return matches