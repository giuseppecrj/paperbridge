import pytest
from src.job_queue import JobQueue, QueueFullError


def test_queue_is_fifo_and_bounded():
    queue = JobQueue(max_pending=2)
    queue.enqueue("first")
    queue.enqueue("second")
    with pytest.raises(QueueFullError):
        queue.enqueue("third")
    assert queue.dequeue() == "first"
    assert queue.status() == {"pending": 1, "capacity": 2}
