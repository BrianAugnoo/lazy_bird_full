import asyncio
import json

from loguru import logger

from lazy_bird.logging_config import traced


def test_console_logs_work_with_a_legacy_windows_encoding(monkeypatch):
    import io
    import sys
    from lazy_bird.logging_config import _console_sink

    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "__stdout__", stream)
    _console_sink("A traceback branch: \u2502\n")
    assert buffer.getvalue().decode("cp1252") == "A traceback branch: \\u2502\n"


def _json_events(messages):
    events = []
    for message in messages:
        for line in message.splitlines():
            if line.startswith("{"):
                events.append(json.loads(line))
    return events


def test_traced_logs_sync_call_return_and_exception():
    messages = []
    sink_id = logger.add(messages.append, format="{message}")

    @traced
    def add(left, right):
        return left + right

    @traced
    def fail():
        raise ValueError("broken")

    try:
        assert add(2, 3) == 5
        try:
            fail()
        except ValueError:
            pass
    finally:
        logger.remove(sink_id)

    output = "\n".join(messages)
    events = _json_events(messages)
    add_call = next(event for event in events if event["function"].endswith(".add") and event["event"] == "function_call")
    add_return = next(event for event in events if event["function"].endswith(".add") and event["event"] == "function_return")
    fail_return = next(event for event in events if event["function"].endswith(".fail") and event["event"] == "function_return")
    assert add_call["call_id"] == add_return["call_id"]
    assert add_return["status"] == "success"
    assert add_return["duration_ms"] >= 0
    assert fail_return["status"] == "error"
    assert add_call["parent_id"] is None
    assert "ValueError: broken" in output


def test_traced_logs_async_call():
    messages = []
    sink_id = logger.add(messages.append, format="{message}")

    @traced
    async def fetch_value():
        return "ready"

    try:
        assert asyncio.run(fetch_value()) == "ready"
    finally:
        logger.remove(sink_id)

    events = _json_events(messages)
    fetch_call = next(event for event in events if event["function"].endswith(".fetch_value") and event["event"] == "function_call")
    fetch_return = next(event for event in events if event["function"].endswith(".fetch_value") and event["event"] == "function_return")
    assert fetch_call["call_id"] == fetch_return["call_id"]
    assert fetch_return["result"] == "'ready'"


def test_traced_parent_id_links_nested_calls():
    messages = []
    sink_id = logger.add(messages.append, format="{message}")

    @traced
    def child():
        return "child"

    @traced
    def parent():
        return child()

    try:
        assert parent() == "child"
    finally:
        logger.remove(sink_id)

    events = _json_events(messages)
    parent_call = next(event for event in events if event["function"].endswith(".parent") and event["event"] == "function_call")
    child_call = next(event for event in events if event["function"].endswith(".child") and event["event"] == "function_call")
    assert child_call["parent_id"] == parent_call["call_id"]


def test_package_function_is_traced_without_decorator():
    import lazy_bird.main as main_module
    from lazy_bird.logging_config import set_package_tracing

    messages = []
    sink_id = logger.add(messages.append, format="{message}")
    set_package_tracing(True)
    try:
        asyncio.run(main_module.health())
    finally:
        set_package_tracing(False)
        logger.remove(sink_id)

    events = _json_events(messages)
    assert any(
        event["event"] == "function_call"
        and event["module"] == "lazy_bird.main"
        and event["function"] == "health"
        for event in events
    )

def test_printed_lines_become_single_log_records():
    from lazy_bird.logging_config import _StreamToLoguru

    messages = []
    sink_id = logger.add(messages.append, format="{message}")
    stream = _StreamToLoguru("INFO")
    try:
        stream.write("value:")
        stream.write(" ")
        stream.write("42")
        stream.write("\n")
        stream.write("pending")
        stream.flush()
    finally:
        logger.remove(sink_id)

    assert [message.strip() for message in messages] == ["value: 42", "pending"]


def test_reading_the_logs_is_not_traced(tmp_path):
    from lazy_bird.log_search import search_logs
    from lazy_bird.logging_config import set_package_tracing

    log_file = tmp_path / "logs.txt"
    log_file.write_text("2026-10-01 21:53:00.000 | INFO     | MainProcess:1 | MainThread:1 | lazy_bird.main:health:1 | started\n", encoding="utf-8")
    messages = []
    sink_id = logger.add(messages.append, format="{message}")
    set_package_tracing(True)
    try:
        search_logs("started", log_file=log_file)
    finally:
        set_package_tracing(False)
        logger.remove(sink_id)

    assert [event for event in _json_events(messages) if event["event"] == "function_call"] == []  # it would write while reading


def test_a_log_file_that_cannot_be_rotated_keeps_growing_instead_of_failing_on_every_line(tmp_path, monkeypatch):
    import io

    import loguru._file_sink as file_sink

    from lazy_bird.logging_config import SizeRotation

    def locked(source, target):  # Windows, when another process has the file open
        raise PermissionError(32, "The file is used by another process", source)

    reports = io.StringIO()
    monkeypatch.setattr(file_sink.os, "rename", locked)
    monkeypatch.setattr("sys.stderr", reports)
    monkeypatch.setattr("sys.__stderr__", reports)
    log_file = tmp_path / "logs.txt"
    sink_id = logger.add(log_file, format="{message}", rotation=SizeRotation(200), catch=True)
    try:
        for index in range(30):
            logger.info(f"line {index:02d} " + "x" * 20)
    finally:
        logger.remove(sink_id)

    written = log_file.read_text(encoding="utf-8")
    assert reports.getvalue().count("--- Logging error in Loguru Handler") == 1  # one failure, not one per line
    assert "could not be rotated" in reports.getvalue()
    assert "line 29" in written and written.count("line ") == 29  # only the line of the failed attempt is lost


def test_a_log_file_is_rotated_past_its_size(tmp_path):
    from lazy_bird.logging_config import SizeRotation

    sink_id = logger.add(tmp_path / "logs.txt", format="{message}", rotation=SizeRotation(200))
    try:
        for index in range(30):
            logger.info(f"line {index:02d} " + "x" * 20)
    finally:
        logger.remove(sink_id)

    assert len(list(tmp_path.glob("logs*.txt"))) > 1
    assert all(path.stat().st_size <= 200 for path in tmp_path.glob("logs*.txt"))


def test_loguru_reports_about_a_failing_sink_reach_the_terminal_without_being_logged(monkeypatch):
    import io

    from lazy_bird.logging_config import _StreamToLoguru

    terminal, records = io.StringIO(), []
    monkeypatch.setattr("sys.__stderr__", terminal)
    sink_id = logger.add(records.append, format="{message}")
    stream = _StreamToLoguru("ERROR")
    try:
        stream.write("--- Logging error in Loguru Handler #2 ---\nRecord was: {...}\nPermissionError: [WinError 32]\n--- End of logging error ---\n")
        stream.write("an ordinary error line\n")
    finally:
        logger.remove(sink_id)

    assert "PermissionError" in terminal.getvalue() and terminal.getvalue().count("\n") == 4
    assert [record.strip() for record in records] == ["an ordinary error line"]


def test_call_tracing_is_off_unless_asked(tmp_path):
    import os
    import subprocess
    import sys

    probe = "import sys, lazy_bird.main, lazy_bird.logging_config as logs; sys.__stdout__.write('tracing=' + str(logs.tracing_enabled()))"  # print() is logged
    environment = {key: value for key, value in os.environ.items() if key != "LAZY_BIRD_TRACE_ALL"}
    environment["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)

    def traced(**extra):
        run = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, capture_output=True, text=True, check=True, env={**environment, **extra})
        return run.stdout.rsplit("tracing=", 1)[1].strip()

    assert traced() == "False"
    assert traced(LAZY_BIRD_TRACE_ALL="1") == "True"
