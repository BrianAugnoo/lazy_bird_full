from datetime import datetime
from pathlib import Path

import pytest

from lazy_bird.log_parser import iter_log_entries, parse_log_file
from lazy_bird.log_search import LogSearchError, search_logs
from lazy_bird.log_tools import main
from lazy_bird.log_tree import trace_function_calls


FIXTURE = Path(__file__).parent / "fixtures" / "logs_fixture.txt"


def test_parser_preserves_ranges_payloads_and_traceback():
    entries = parse_log_file(FIXTURE)

    assert len(entries) == 9
    assert entries[5].start_line == 6
    assert entries[5].end_line == 10
    assert entries[5].payload["status"] == "error"
    assert "ValueError: broken" in entries[5].message
    assert entries[-1].payload is None


def test_search_supports_bm25_regex_dates_and_last_n():
    bm25_matches = search_logs("createAPIKey", log_file=FIXTURE)
    assert [entry.payload["call_id"] for entry in bm25_matches] == ["child1", "child1"]
    regex_matches = search_logs(r"status\":\"error", mode="regex", log_file=FIXTURE)
    assert [entry.payload["call_id"] for entry in regex_matches] == ["error1"]
    dated = search_logs(
        None,
        since=datetime(2026, 10, 1, 21, 53),
        until=datetime(2026, 10, 1, 21, 54),
        last_n=1,
        log_file=FIXTURE,
    )
    assert dated[0].payload["call_id"] == "interrupted"


def test_search_validation_errors_are_explicit():
    with pytest.raises(LogSearchError, match="requête"):
        search_logs(log_file=FIXTURE)
    with pytest.raises(LogSearchError, match="Expression régulière invalide"):
        search_logs("[", mode="regex", log_file=FIXTURE)


def test_trace_tree_handles_success_error_interrupted_and_raw():
    tree = trace_function_calls("root_call", log_file=FIXTURE)
    assert "lazy_bird.api.root_call" in tree
    assert "    lazy_bird.crud.createAPIKey" in tree
    raw = trace_function_calls("broken_call", raw=True, log_file=FIXTURE)
    assert "6: 2026-10-01" in raw
    assert "ValueError: broken" in raw
    interrupted = trace_function_calls("interrupted_call", log_file=FIXTURE)
    assert "INTERROMPU" in interrupted


def test_cli_exit_codes_and_json(capsys):
    assert main(["search", "createAPIKey", "--log-file", str(FIXTURE), "--json"]) == 0
    assert '"ok": true' in capsys.readouterr().out
    assert main(["search", "nothing", "--log-file", str(FIXTURE)]) == 1
    assert main(["search", "--log-file", str(FIXTURE)]) == 2
    assert main(["search", "x", "--log-file", str(FIXTURE.with_name("missing.log"))]) == 3

def test_reading_a_log_that_grows_meanwhile_ends_with_what_it_held(tmp_path):
    log_file = tmp_path / "logs.txt"
    log_file.write_bytes(FIXTURE.read_bytes())
    entries = iter_log_entries(log_file)

    first = next(entries)
    with log_file.open("a", encoding="utf-8") as appending:  # what the server writes while its log is read
        appending.write(FIXTURE.read_text(encoding="utf-8"))
    rest = list(entries)

    assert len([first, *rest]) == 9


def test_a_log_being_read_can_be_rotated(tmp_path):
    log_file = tmp_path / "logs.txt"
    log_file.write_bytes(FIXTURE.read_bytes())
    entries = iter_log_entries(log_file)
    next(entries)

    log_file.rename(tmp_path / "logs.1.txt")  # Windows refuses to rename a file that is open

    assert len(list(entries)) == 8


def test_windows_line_ends_are_read_like_plain_ones(tmp_path):
    log_file = tmp_path / "logs.txt"
    log_file.write_bytes(FIXTURE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))

    assert [entry.message for entry in parse_log_file(log_file)] == [entry.message for entry in parse_log_file(FIXTURE)]
