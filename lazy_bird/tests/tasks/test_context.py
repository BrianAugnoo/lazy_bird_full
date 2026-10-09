"""What a task function can do with its context while it waits for work it cannot interrupt."""

import threading

import pytest

from lazy_bird.tasks.context import TaskContext
from lazy_bird.tasks.registry import TaskCancelled, TaskPaused


class Controls:
    """The scheduler, as a context sees it: the pending control of the task."""

    def __init__(self) -> None:
        self.control = None

    def control_of(self, task_id):
        return self.control

    def record_progress(self, task_id, progress, message, state):
        pass


def test_a_blocking_call_gives_its_result_or_its_error():
    context = TaskContext(1, {}, {}, Controls())

    assert context.run_blocking(lambda a, b=0: a + b, 2, b=3) == 5
    with pytest.raises(ZeroDivisionError):
        context.run_blocking(lambda: 1 / 0)


@pytest.mark.parametrize(("control", "stop"), [("cancel", TaskCancelled), ("pause", TaskPaused)])
def test_a_task_waiting_for_a_blocking_call_stops_when_asked(control, stop):
    controls = Controls()
    context = TaskContext(1, {}, {}, controls)
    never = threading.Event()
    threading.Timer(0.1, lambda: setattr(controls, "control", control)).start()

    with pytest.raises(stop):
        context.run_blocking(never.wait, 30)
    never.set()


def test_run_inline_a_blocking_call_is_a_plain_call():
    assert TaskContext.detached({}).run_blocking(threading.current_thread) is threading.current_thread()
