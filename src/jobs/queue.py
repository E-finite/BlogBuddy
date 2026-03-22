"""Simple in-process job queue."""
import queue
import logging

logger = logging.getLogger(__name__)

# Global job queue
_job_queue = queue.Queue()


def enqueue_job(job_id: str, job_type: str, payload: dict) -> None:
    """Add a job to the queue."""
    _job_queue.put({
        "id": job_id,
        "type": job_type,
        "payload": payload
    })
    logger.info(f"Job {job_id} enqueued")


def dequeue_job(timeout: float = 1.0):
    """Get a job from the queue (blocks with timeout)."""
    try:
        return _job_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def queue_size() -> int:
    """Get the current queue size."""
    return _job_queue.qsize()
