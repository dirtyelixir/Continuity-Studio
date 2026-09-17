import json
from studio import store
from test_production import client


def test_saved_proposal_progress_in_detail_and_project_is_read_only(client):
    pid = client.post('/api/projects', json={'title': 'Progress', 'idea': 'A lamp'}).json()['id']
    jid = 'proposal-progress-api'
    work = store.DATA / 'jobs' / jid
    work.mkdir(parents=True)
    candidate = {'shots': [{'id': 'shot_01'}, {'id': 'shot_02'}]}
    (work / 'result.json').write_text(json.dumps(candidate))
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,created,updated) VALUES(?,?,?,?,?,?,?,?,?)',
                  (jid, pid, 'narrative', '', 'running', 'astra', '{}', store.now(), store.now()))
    before = store.job(jid)
    detail = client.get('/api/jobs/' + jid)
    project = client.get('/api/projects/' + pid)
    assert detail.status_code == project.status_code == 200
    progress = detail.json()['progress']
    assert progress['kind'] == 'proposal_validation'
    assert progress['total_shots'] == 2
    assert progress['completed_shots'] == 0
    assert next(j for j in project.json()['jobs'] if j['id'] == jid)['progress'] == progress
    assert store.job(jid) == before
    assert json.loads((work / 'result.json').read_text()) == candidate
