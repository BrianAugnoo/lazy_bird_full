import asyncio

from loguru import logger

from lazy_bird.logging_config import traced


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
    assert "CALL function test_traced_logs_sync_call_return_and_exception.<locals>.add" in output
    assert "RETURN function test_traced_logs_sync_call_return_and_exception.<locals>.add" in output
    assert "status=success duration_ms=" in output
    assert "ERROR function test_traced_logs_sync_call_return_and_exception.<locals>.fail" in output
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

    output = "\n".join(messages)
    assert "CALL function test_traced_logs_async_call.<locals>.fetch_value" in output
    assert "RETURN function test_traced_logs_async_call.<locals>.fetch_value" in output