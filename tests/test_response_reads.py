from contextlib import contextmanager
from studio import store
from studio.app import state
from test_production import client, plan


def test_project_response_reuses_history_without_changing_output(client, plan, monkeypatch):
    pid=client.post('/api/projects',json={'title':'Response test','idea':'test'}).json()['id']
    with store.db() as c:
        c.execute('UPDATE projects SET production=? WHERE id=?',(store.encode(plan),pid))
    original=store.db
    reads=[]
    @contextmanager
    def counted():
        with original() as c:
            c.set_trace_callback(lambda sql: reads.append(sql) if sql.startswith('SELECT * FROM jobs WHERE') else None)
            yield c
    monkeypatch.setattr(store,'db',counted)
    uncached=state.__wrapped__(pid)
    assert len(reads)>1
    reads.clear()
    assert state(pid)==uncached
    assert len(reads)==1
    reads.clear()
    assert state(pid)==uncached
    assert len(reads)==1, 'Each response must read fresh history'


def test_read_scope_resets_after_failure_and_does_not_leak(client):
    @store.reuse_job_reads
    def failed():
        store.jobs('missing')
        raise ValueError('test')
    import pytest
    with pytest.raises(ValueError): failed()
    assert store._job_reads.get() is None
