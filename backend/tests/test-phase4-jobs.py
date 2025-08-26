import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

# Ensure tests can import the application package when running from backend/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Ensure environment variables for test DB are set before importing app/config
os.environ.setdefault('MONGO_URI', os.environ.get('MONGO_URI', 'mongodb://localhost:27017'))
os.environ.setdefault('MONGO_DB', 'lawchronicle_test_db')

from main import app
from app.core.config import Settings
from app.core.auth import get_current_user


client = TestClient(app)


def get_test_db_client():
    from pymongo import MongoClient
    settings = Settings()
    return MongoClient(settings.mongodb_url)


def test_enqueue_and_worker_processes_job(monkeypatch):
    # Prepare test DB
    db_client = get_test_db_client()
    test_db = db_client.get_database('lawchronicle_test_db')

    test_db.drop_collection('statutes')
    test_db.drop_collection('date_processed_statutes')
    test_db.drop_collection('phase4_jobs')
    # Also clean default 'Statutes' DB to avoid processing other queued jobs
    db_client.get_database('Statutes').drop_collection('statutes')
    db_client.get_database('Statutes').drop_collection('date_processed_statutes')
    db_client.get_database('Statutes').drop_collection('phase4_jobs')

    # Insert sample statute
    sample = {
        'name': 'Test Statute 1',
        'text': 'Statute text with possible date 01-Jan-1940',
    }
    test_db.get_collection('statutes').insert_one(sample)

    # Enqueue job
    # Bypass auth for test by overriding dependency
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "test-user"}
    resp = client.post('/api/v1/phase4/start-processing')
    assert resp.status_code == 200
    body = resp.json()
    assert body.get('success') is True
    job_id = body.get('job_id')
    assert job_id

    # Job may be persisted to the service's configured DB (often 'Statutes') or to our test DB.
    job_doc = test_db.get_collection('phase4_jobs').find_one({'job_id': job_id})
    if not job_doc:
        # fallback to default 'Statutes' DB where Phase4Service writes by default
        job_doc = db_client.get_database('Statutes').get_collection('phase4_jobs').find_one({'job_id': job_id})
    assert job_doc is not None
    assert job_doc.get('status') == 'queued'

    # Run worker iteration
    from app.core.services.phase4_worker import run_worker_iteration

    processed_job_id = run_worker_iteration()
    assert processed_job_id is not None
    assert processed_job_id == job_id

    # Small wait to allow db to update
    time.sleep(0.2)

    job_after = test_db.get_collection('phase4_jobs').find_one({'job_id': job_id})
    if not job_after:
        job_after = db_client.get_database('Statutes').get_collection('phase4_jobs').find_one({'job_id': job_id})
    assert job_after is not None
    assert job_after.get('status') in ('completed', 'failed', 'running')

    # Cleanup both DBs
    test_db.drop_collection('statutes')
    test_db.drop_collection('date_processed_statutes')
    test_db.drop_collection('phase4_jobs')
    db_client.get_database('Statutes').drop_collection('statutes')
    db_client.get_database('Statutes').drop_collection('date_processed_statutes')
    db_client.get_database('Statutes').drop_collection('phase4_jobs')
    # drop persisted date records
    try:
        test_db.drop_collection('phase4_date_records')
    except Exception:
        pass
    try:
        db_client.get_database('Statutes').drop_collection('phase4_date_records')
    except Exception:
        pass
    # Remove dependency override
    app.dependency_overrides.pop(get_current_user, None)
