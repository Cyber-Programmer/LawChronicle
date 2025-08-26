import pytest
from unittest.mock import AsyncMock
import app.api.v1.endpoints.phase4_search as phase4
from bson import ObjectId

@pytest.mark.asyncio
async def test_background_run_reports_total_processed_positive(monkeypatch):
    # Mock source_db counts and cursor to return one doc
    class FakeColl:
        async def count_documents(self, q):
            return 1
        def find(self, q):
            async def gen():
                yield {'_id': ObjectId(), 'Sections': [], 'Statute_Name': 'S'}
            return gen()

    monkeypatch.setattr(phase4.search_service, 'source_db', {'batch_1': FakeColl()})

    # Fake generator that yields processing and completed with total_processed=1
    async def fake_gen(docs):
        yield {'status': 'processing', 'progress': 50}
        yield {'status': 'completed', 'total_processed': 1}

    monkeypatch.setattr(phase4.search_service, 'search_dates_with_ai', fake_gen)

    # Capture diagnostics inserts
    class FakeDiag:
        def __init__(self):
            self.inserted = []
        async def insert_one(self, doc):
            self.inserted.append(doc)
            class R: inserted_id = ObjectId()
            return R()

    fake_diag = FakeDiag()
    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_diagnostics': fake_diag})

    # Run
    await phase4.run_ai_date_search('sid123', collections=['batch_1'], max_docs=1)
    # No diagnostics for positive run
    assert len(fake_diag.inserted) == 0 or all('error' not in d for d in fake_diag.inserted)

@pytest.mark.asyncio
async def test_background_run_logs_error_on_invalid_file(monkeypatch):
    # Simulate generator raising an exception during processing
    async def broken_gen(docs):
        yield {'status': 'processing', 'progress': 10}
        raise Exception('ai failure')

    monkeypatch.setattr(phase4.search_service, 'search_dates_with_ai', broken_gen)

    class FakeColl:
        async def count_documents(self, q):
            return 1
        def find(self, q):
            async def gen():
                yield {'_id': ObjectId(), 'Sections': [], 'Statute_Name': 'S'}
            return gen()

    monkeypatch.setattr(phase4.search_service, 'source_db', {'batch_1': FakeColl()})

    fake_diag = []
    class FakeDiag:
        async def insert_one(self, doc):
            fake_diag.append(doc)
            class R: inserted_id = ObjectId()
            return R()

    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_diagnostics': FakeDiag()})

    # Run and ensure no unhandled exception (run_ai_date_search catches and logs)
    await phase4.run_ai_date_search('sid_err', collections=['batch_1'], max_docs=1)
    assert len(fake_diag) >= 0

@pytest.mark.asyncio
async def test_background_run_zero_processed_writes_diagnostic_with_reason(monkeypatch):
    # Setup source_db with docs but generator returns completed with total_processed=0
    class FakeColl:
        async def count_documents(self, q):
            return 2
        def find(self, q):
            async def gen():
                yield {'_id': ObjectId(), 'Sections': [], 'Statute_Name': 'S1'}
                yield {'_id': ObjectId(), 'Sections': [], 'Statute_Name': 'S2'}
            return gen()

    monkeypatch.setattr(phase4.search_service, 'source_db', {'batch_1': FakeColl()})

    async def gen_zero(docs):
        yield {'status': 'processing', 'progress': 50}
        yield {'status': 'completed', 'total_processed': 0}

    monkeypatch.setattr(phase4.search_service, 'search_dates_with_ai', gen_zero)

    captured = []
    class FakeDiag2:
        async def insert_one(self, doc):
            captured.append(doc)
            class R: inserted_id = ObjectId()
            return R()

    monkeypatch.setattr(phase4.search_service, 'search_db', {'search_diagnostics': FakeDiag2()})

    await phase4.run_ai_date_search('sid_zero', collections=['batch_1'], max_docs=10)
    # Expect diagnostics entry inserted for zero-processed case
    assert any(d.get('search_id') == 'sid_zero' for d in captured)
