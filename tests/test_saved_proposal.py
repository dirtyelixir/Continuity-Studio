import json
from studio import store
from test_production import client


def test_failed_candidate_preview_is_read_only_and_exposes_recovery_block(client):
    pid=client.post('/api/projects',json={'title':'Saved','idea':'A lamp'}).json()['id']
    jid='saved-preview';work=store.DATA/'jobs'/jid;work.mkdir(parents=True)
    raw={'title':'Draft','story':'Retained story','screenplay':'Retained script','canon':[{}]*4,'scenes':[{}],'shots':[{}]*3}
    (work/'result.json').write_text(json.dumps(raw))
    check=work/'canonical-state'/'test';check.mkdir(parents=True)
    (check/'receipt.json').write_text(json.dumps({'state':'blocked','error':'Missing revision intent'}))
    (check/'source.json').write_text(json.dumps({'shot':{'id':'shot_02'}}))
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,error,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (jid,pid,'narrative','','failed','astra','{}','Original validation error',store.now(),store.now()))
    before=store.job(jid)
    result=client.get('/api/jobs/'+jid)
    assert result.status_code==200
    saved=result.json()['saved_proposal']
    assert saved['story']=='Retained story' and saved['shots']==3 and saved['canon']==4
    assert saved['checks']==[{'shot_id':'shot_02','state':'blocked','error':'Missing revision intent'}]
    assert result.json()['result'] is None and store.job(jid)==before
    assert json.loads((work/'result.json').read_text())==raw
    (work/'result.json').write_text('{incomplete')
    assert client.get('/api/jobs/'+jid).json()['saved_proposal'] is None
    assert store.job(jid)==before
