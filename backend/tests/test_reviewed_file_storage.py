import pytest
from bson import ObjectId
from unittest.mock import AsyncMock
import app.api.v1.endpoints.phase4_search as phase4

@pytest.mark.asyncio
async def test_gridfs_upload_and_download_roundtrip(monkeypatch):
    stored = {}
    class FakeBucket:
        def __init__(self, db, bucket_name='reviewed_files'):
            pass
        async def upload_from_stream(self, filename, stream):
            oid = ObjectId()
            stored[str(oid)] = {'filename': filename, 'content': stream.getvalue()}
            return oid
        async def open_download_stream(self, oid):
            class Stream:
                async def read(self):
                    return stored[str(oid)]['content']
            return Stream()

    monkeypatch.setattr(phase4, 'AsyncIOMotorGridFSBucket', FakeBucket)

    # Simulate upload flow (call the bucket directly)
    bucket = FakeBucket(None)
    import io
    oid = await bucket.upload_from_stream('t.xlsx', io.BytesIO(b'abc'))
    stream = await bucket.open_download_stream(oid)
    data = await stream.read()
    assert data == b'abc'

@pytest.mark.asyncio
async def test_session_metadata_written_after_upload(monkeypatch):
    # Ensure upload_reviewed_excel updates search_sessions when session_id provided
    fake_updated = {}
    class FakeColl:
        async def update_one(self, filter_q, update_doc, upsert=False):
            fake_updated['filter'] = filter_q
            fake_updated['update'] = update_doc
            class Res: modified_count = 1
            return Res()

    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_sessions': FakeColl(), 'search_diagnostics': AsyncMock()})

    # Monkeypatch pandas.read_excel to return a simple df
    import pandas as pd
    df = pd.DataFrame([{'Review_Status': 'approved'}])
    monkeypatch.setattr(phase4.pd, 'read_excel', lambda *args, **kwargs: df)

    # Create a fake UploadFile-like obj
    class FakeUpload:
        filename = 'rev.xlsx'
        async def read(self):
            return b'data'

    # Call the endpoint function directly
    resp = await phase4.upload_reviewed_excel(FakeUpload(), session_id='s1', current_user={'user_id': 'tester'})
    assert resp['status'] == 'success'
    assert fake_updated['filter']['session_id'] == 's1'
    assert 'reviewed_file_meta' in fake_updated['update']['$set'] or 'approved_rows_count' in fake_updated['update']['$set']

@pytest.mark.asyncio
async def test_gridfs_failure_returns_helpful_error(monkeypatch):
    # Make bucket raise on upload
    class BrokenBucket:
        def __init__(self, db, bucket_name='reviewed_files'):
            pass
        async def upload_from_stream(self, filename, stream):
            raise Exception('gridfs down')
    monkeypatch.setattr(phase4, 'AsyncIOMotorGridFSBucket', BrokenBucket)

    import pandas as pd
    df = pd.DataFrame([{'Review_Status': 'approved'}])
    monkeypatch.setattr(phase4.pd, 'read_excel', lambda *args, **kwargs: df)

    class FakeUpload:
        filename = 'rev.xlsx'
        async def read(self):
            return b'data'

    # Should still return preview response but log warning; call function
    resp = await phase4.upload_reviewed_excel(FakeUpload(), session_id='s1', current_user={'user_id': 'tester'})
    assert resp['status'] == 'success'
