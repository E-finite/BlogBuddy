"""Background worker for processing jobs."""
import threading
import logging
import time
from src import db
from src.jobs.queue import dequeue_job
from src.jobs.publish_job import execute_publish_job

logger = logging.getLogger(__name__)

_worker_running = False
_worker_thread = None


def start_worker():
    """Start the background worker thread."""
    global _worker_running, _worker_thread

    if _worker_running:
        logger.warning("Worker already running")
        return

    _worker_running = True
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
    _worker_thread.start()
    logger.info("Background worker started")


def stop_worker():
    """Stop the background worker."""
    global _worker_running
    _worker_running = False
    logger.info("Background worker stopped")


def _worker_loop():
    """Main worker loop."""
    global _worker_running

    while _worker_running:
        try:
            # Check for queued jobs in database
            queued_jobs = db.get_queued_jobs()

            for job_data in queued_jobs:
                job_id = job_data["id"]
                job_type = job_data["type"]
                job = db.get_job(job_id)
                if not job or "payload" not in job:
                    logger.error(f"Job {job_id} not found or missing payload")
                    db.update_job(job_id, "failed", error={
                                  "error": "Job not found or missing payload"})
                    continue
                payload = job["payload"]

                # Mark as running
                db.update_job(job_id, "running")
                db.add_job_step(job_id, "start", "running")

                try:
                    # Execute job based on type
                    if job_type == "publish":
                        result = execute_publish_job(job_id, payload)

                        # Determine final status
                        if result.get("errors"):
                            if result.get("wpPostIds"):
                                status = "partial_success"
                            else:
                                status = "failed"
                        else:
                            status = "success"

                        db.update_job(job_id, status, result=result)
                        db.add_job_step(job_id, "complete", status, result)
                        
                        # Cleanup images after successful publish
                        if status == "success":
                            try:
                                deleted_count = db.cleanup_job_images(job_id)
                                if deleted_count > 0:
                                    logger.info(f"Cleaned up {deleted_count} image(s) for job {job_id}")
                            except Exception as cleanup_error:
                                logger.warning(f"Image cleanup failed for job {job_id}: {cleanup_error}")
                                # Don't fail the job if cleanup fails
                    else:
                        raise ValueError(f"Unknown job type: {job_type}")

                except Exception as e:
                    logger.error(
                        f"Error executing job {job_id}: {e}", exc_info=True)
                    db.update_job(job_id, "failed", error={
                                  "error": str(e), "type": type(e).__name__})
                    db.add_job_step(job_id, "complete",
                                    "failed", {"error": str(e)})

            # Sleep if no jobs
            if not queued_jobs:
                time.sleep(2)
            else:
                time.sleep(0.5)  # Small delay between jobs

        except Exception as e:
            logger.error(f"Error in worker loop: {e}", exc_info=True)
            time.sleep(5)  # Wait longer on error
