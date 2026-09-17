import json
import os
import pytest
from studio import store, proposal_progress


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'DATA', tmp_path)
    return tmp_path / 'jobs' / 'j'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def job(**kwargs):
    return {'id': 'j', 'state': 'running', 'capability': 'narrative', **kwargs}


def attempt(work, name, sid, state='attempted'):
    folder = work / 'canonical-state' / name
    write(folder / 'source.json', {'shot': {'id': sid}})
    write(folder / 'receipt.json', {'state': state})
    return folder


def test_missing_partial_and_terminal(work):
    assert '尚未有已保存結果' in proposal_progress.progress(job())['label']
    assert not work.exists()
    for state in ('queued', 'succeeded', 'failed', 'interrupted', 'cancelled'):
        assert proposal_progress.progress(job(state=state)) is None
    assert proposal_progress.progress(job(capability='image')) is None
    write(work / 'result.json', {})
    (work / 'result.json').write_text('{partial')
    assert '尚未有已保存結果' in proposal_progress.progress(job())['label']
    write(work / 'result.json', {'production': []})
    assert '驗證方案格式' in proposal_progress.progress(job())['label']


@pytest.mark.parametrize('wrapped', [False, True])
def test_saved_candidate_and_stages(work, wrapped):
    plan = {'shots': [{'id': 's1'}, {'id': 's2'}]}
    write(work / 'result.json', {'production': plan} if wrapped else plan)
    assert proposal_progress.progress(job())['total_shots'] == 2
    folder = attempt(work, 'first', 's1')
    assert '正在整理鏡頭狀態' in proposal_progress.progress(job())['label']
    write(folder / 'extract-repair/request.txt', 'request')
    assert '正在修正鏡頭狀態格式' in proposal_progress.progress(job())['label']
    write(folder / 'check/request.txt', 'request')
    assert '正在獨立核對' in proposal_progress.progress(job())['label']
    write(folder / 'receipt.json', {'state': 'accepted'})
    assert proposal_progress.progress(job())['completed_shots'] == 1
    write(work / 'canonical-production.json', plan)
    assert proposal_progress.progress(job())['completed_shots'] == 2
    assert '驗證已完成' in proposal_progress.progress(job())['label']


def test_latest_attempt_dedup_foreign_and_malformed(work):
    write(work / 'result.json', {'shots': [{'id': 's1'}, {'id': 's2'}]})
    old = attempt(work, 'old', 's1', 'blocked')
    for path in old.iterdir(): os.utime(path, ns=(1, 1))
    attempt(work, 'new', 's1', 'accepted')
    attempt(work, 'foreign', 's3', 'accepted')
    current = attempt(work, 'current', 's2')
    (current / 'receipt.json').write_text('{partial')
    p = proposal_progress.progress(job())
    assert p['completed_shots'] == 1 and p['current_shot_id'] == 's2'
    assert '未通過' not in p['label']
    write(current / 'receipt.json', {'state': 'blocked'})
    write(work / 'recovery-attempts' / 'r' / 'receipt.json', {'state': 'running'})
    p = proposal_progress.progress(job())
    assert '恢復已保存方案' in p['label'] and '未通過' in p['label']
    # A newer failed attempt must supersede old accepted evidence for the same shot.
    fresh = attempt(work, 'newest', 's1', 'failed')
    assert proposal_progress.progress(job())['completed_shots'] == 0
    (fresh / 'source.json').write_text('[]')
    assert proposal_progress.progress(job())['completed_shots'] == 1


def test_storyboard_repaired_candidate(work):
    write(work / 'result.json', {'shots': [{'id': 'old'}]})
    write(work / 'repair-1' / 'result.json', {'shots': [{'id': 's1'}, {'id': 's2'}]})
    assert proposal_progress.progress(job(capability='storyboard'))['total_shots'] == 2
