"""
Minimal Phase4 worker scaffold - polls 'phase4_jobs' collection for queued jobs and runs them.
Run manually: python -m app.core.services.phase4_worker
"""
import time
import logging
from pymongo import MongoClient
from .phase4_service import Phase4Service
from ..config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def run_worker_iteration():
    """Run a single iteration of the worker loop: pick one queued job and process it.

    Returns True if a job was found and handled, False if no queued job was present.
    """
    client = MongoClient(settings.mongodb_url)
    db = client[settings.mongodb_db]
    jobs = db.get_collection('phase4_jobs')
    service = Phase4Service(mongo_uri=settings.mongodb_url)

    job = jobs.find_one({'status': 'queued'})
    if not job:
        return None

    job_id = job.get('job_id')
    logger.info(f'Picking up job {job_id}')
    try:
        jobs.update_one({'job_id': job_id}, {'$set': {'status': 'running', 'started_at': time.time()}})
        service.process_database_immediate()
        jobs.update_one({'job_id': job_id}, {'$set': {'status': 'completed', 'completed_at': time.time()}})
        logger.info(f'Job {job_id} completed')
    except Exception as e:
        logger.exception(f'Job {job_id} failed: {e}')
        jobs.update_one({'job_id': job_id}, {'$set': {'status': 'failed', 'error': str(e), 'completed_at': time.time()}})
    return job_id


def run_worker(poll_interval=5):
    logger.info('Phase4 worker started, polling for jobs...')
    while True:
        handled = run_worker_iteration()
        if not handled:
            time.sleep(poll_interval)

if __name__ == '__main__':
    run_worker()
