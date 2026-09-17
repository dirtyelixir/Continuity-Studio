import copy
from studio import prompt_preparation,store
from test_production import client,plan,create
from test_prompt_preparation import result_for,save_result


def test_scope_changes_reuse_legacy_preparation_but_voice_changes_do_not(client,plan):
    legacy=prompt_preparation.source(plan,'scene')
    assert all('scope' not in e for e in legacy['canon'])
    pid=create(client,plan)
    save_result(pid,result_for(plan),legacy)
    p=store.project(pid)
    p['production']['canon'][0]['scope']='public'
    assert prompt_preparation.prepared(p,'scene')[1]['status']=='ready'
    p['production']['canon'][0]['kind']='voice'
    assert prompt_preparation.prepared(p,'scene')[0] is None


def test_rollout_preparation_reuse_requires_complete_unchanged_source(client,plan):
    pid=create(client,plan)
    p=store.project(pid)
    source=prompt_preparation.source(p['production'],'scene')
    for e in source['canon']:e['scope']='auto'
    result=result_for(plan)
    jid=store.uid()
    with store.db() as c:
        c.execute('INSERT INTO jobs(id,project_id,capability,target_id,state,provider,input,result,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',(jid,pid,'h3_prepare','scene','succeeded','test',store.encode({'preparation_source':source,'preparation_hash':store.digest(source)}),store.encode(result),store.now(),store.now()))
    p['production']['canon'][0]['scope']='public'
    assert prompt_preparation.prepared(p,'scene')[1]['status']=='ready'
    changed=copy.deepcopy(p)
    changed['production']['shots'][0]['action']='Different action'
    assert prompt_preparation.prepared(changed,'scene')[0] is None
    with store.db() as c:c.execute('UPDATE jobs SET input=? WHERE id=?',(store.encode({'preparation_source':source,'preparation_hash':'wrong'}),jid))
    assert prompt_preparation.prepared(p,'scene')[0] is None
