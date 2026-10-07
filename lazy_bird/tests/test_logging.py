import asyncio
import json

from loguru import logger

from lazy_bird.logging_config import traced


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
