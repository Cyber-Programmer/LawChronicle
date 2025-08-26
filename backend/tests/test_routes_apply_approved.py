import io
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

import importlib.util
import sys
from pathlib import Path

# Load backend main.py as a module to get the FastAPI app reliably in test runs
root = Path(__file__).resolve().parents[1]
main_path = root / 'main.py'
spec = importlib.util.spec_from_file_location('backend_main', str(main_path))
backend_main = importlib.util.module_from_spec(spec)
sys.modules['backend_main'] = backend_main
# Ensure backend directory is on sys.path so 'import app' resolves to backend/app
sys.path.insert(0, str(root))
spec.loader.exec_module(backend_main)
app = getattr(backend_main, 'app')

import app.api.v1.endpoints.phase4_search as phase4

@pytest.mark.asyncio
async def test_upload_reviewed_file_stores_gridfs_and_links_session(monkeypatch):
    fake_bytes = b'PK\x03\x04fakeexcel'
    # Monkeypatch pandas.read_excel to return a simple DataFrame-like object
    import pandas as pd
    df = pd.DataFrame([{'Collection': 'batch_1', 'Document_ID': '507f1f77bcf86cd799439011', 'Review_Status': 'approved', 'Approved_Date': '2025-07-01'}])
    monkeypatch.setattr(phase4.pd, 'read_excel', lambda *args, **kwargs: df)

    stored = {}
    class FakeBucket:
        def __init__(self, db, bucket_name='reviewed_files'):
            pass
        async def upload_from_stream(self, filename, stream):
            oid = ObjectId()
            stored[str(oid)] = {'filename': filename, 'content': stream.getvalue()}
            return oid

    # Patch motor's AsyncIOMotorGridFSBucket used by the endpoint module
    monkeypatch.setattr('motor.motor_asyncio.AsyncIOMotorGridFSBucket', FakeBucket)

    class FakeColl:
        async def update_one(self, filter_q, update_doc, upsert=False):
            # ensure we get session_id in filter
            assert 'session_id' in filter_q
            return

    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_sessions': FakeColl(), 'search_diagnostics': AsyncMock()})

    async with AsyncClient(app=app, base_url='http://test') as ac:
        files = {'file': ('reviewed.xlsx', io.BytesIO(fake_bytes), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        resp = await ac.post('/api/v1/phase4/search/upload-reviewed-excel?session_id=test_session_1', files=files)
        assert resp.status_code == 200
        body = resp.json()
        assert body['status'] == 'success'

@pytest.mark.asyncio
async def test_apply_by_session_id_reads_stored_file_and_applies(monkeypatch):
    # Prepare fake GridFS download and a stored session doc
    fake_oid = ObjectId()
    class FakeBucket2:
        def __init__(self, db, bucket_name='reviewed_files'):
            pass
        async def open_download_stream(self, file_oid):
            class Stream:
                async def read(self):
                    return b'fake-bytes'
            return Stream()

    monkeypatch.setattr('motor.motor_asyncio.AsyncIOMotorGridFSBucket', FakeBucket2)

    # Patch pandas to return approved row(s)
    import pandas as pd
    df = pd.DataFrame([{'Collection': 'batch_1', 'Document_ID': '507f1f77bcf86cd799439011', 'Review_Status': 'approved', 'Approved_Date': '2025-07-01'}])
    monkeypatch.setattr(phase4.pd, 'read_excel', lambda *args, **kwargs: df)

    class FakeSessions:
        async def find_one(self, q):
            return {'session_id': 'session_with_file', 'reviewed_file_meta': {'file_id': str(fake_oid), 'filename': 'reviewed.xlsx'}}

    class FakeSourceColl:
        async def update_one(self, q, update):
            class Res: modified_count = 1
            return Res()

    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_sessions': FakeSessions(), 'search_diagnostics': AsyncMock()})
    monkeypatch.setattr(phase4.search_service, 'source_db', {'batch_1': FakeSourceColl()})

    # Override FastAPI dependency to bypass auth checks
    app.dependency_overrides[phase4.get_current_user_with_roles] = lambda: {'sub': 'test', 'roles': ['admin']}

    async with AsyncClient(app=app, base_url='http://test') as ac:
        resp = await ac.post('/api/v1/phase4/search/apply-approved-dates', json={'session_id': 'session_with_file'})
        assert resp.status_code == 200
        body = resp.json()
        assert 'applied' in body

@pytest.mark.asyncio
async def test_apply_with_invalid_session_id_returns_error(monkeypatch):
    class FakeSessions2:
        async def find_one(self, q):
            return None
    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_sessions': FakeSessions2(), 'search_diagnostics': AsyncMock()})

    app.dependency_overrides[phase4.get_current_user_with_roles] = lambda: {'sub': 'test', 'roles': ['admin']}

    async with AsyncClient(app=app, base_url='http://test') as ac:
        resp = await ac.post('/api/v1/phase4/search/apply-approved-dates', json={'session_id': 'no_such'})
        assert resp.status_code in (400, 404)
    app.dependency_overrides.pop(phase4.get_current_user_with_roles, None)
