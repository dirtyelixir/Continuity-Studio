import copy, io, json, zipfile
import pytest
from studio import store, guidance, models, providers
from test_production import client, plan, create


def setup(client, plan):
    plan['shots'][0]['transition_note']='Hard cut to a close-up.'
    second=copy.deepcopy(plan['shots'][0]);second.update(id='shot2',title='Closer',framing='Close-up',keyframes=[{'id':'second','moment':'start','description':'Close-up'}])
    plan['shots'].append(second)
    pid=create(client,plan)
    client.post('/api/settings/routing',json={'capability':'h3_guidance','provider_id':'manual'})
    return pid


def review(client,pid,decision='cut'):
    j=client.post('/api/projects/'+pid+'/guidance/analyze').json()['job']
    assert client.post('/api/projects/'+pid+'/guidance/analyze').json()['job_id']==j['id']
    result={'decisions':[{'shot_id':'shot','previous_shot_id':None,'decision':'start','reason':'第一個鏡頭，沒有上段。','evidence':['Medium']},
                         {'shot_id':'shot2','previous_shot_id':'shot','decision':decision,'reason':'由中景硬切到特寫，保留角色及動作狀態，不延長上一鏡頭。','evidence':['Hard cut to a close-up.','Close-up']}]}
    return j,result


def test_fresh_decision_and_export_then_prompt_edit_invalidates(client,plan):
    pid=setup(client,plan)
    before=client.get('/api/projects/'+pid).json();c=before['delivery']['scenes'][0]['chapters'][1]
    assert c['guidance']['continuityFromPrev'] is None and c['guidance']['decision']=='pending'
    j,result=review(client,pid)
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    p=client.get('/api/projects/'+pid).json();g=p['delivery']['scenes'][0]['chapters'][1]['guidance']
    assert g['decision']=='cut' and g['recommended'] is False and g['enabled'] is False
    assert g['reason']==result['decisions'][1]['reason'] and g['review_provider']=='manual'
    assert p['production']==before['production'] and p['revision']==before['revision']
    assert client.post('/api/projects/'+pid+'/guidance/analyze').json()['status']=='ready'
    z=zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content))
    exported=json.loads(z.read('ref2/scenes/scene/chapters/shot2/references-and-guidance.json'))
    assert exported['guidance']['decision']=='cut' and exported['guidance']['continuityFromPrev'] is False
    cfg=p['delivery']['configuration'];cfg['production_revision']=p['revision'];cfg['scenes']={'scene':{'chapters':{'shot2':{'shot_prompt':'Changed camera direction'}}}}
    assert client.put('/api/projects/'+pid+'/delivery',json=cfg).status_code==200
    fresh=client.get('/api/projects/'+pid).json()['delivery']
    assert fresh['guidance_review']['status']=='pending'
    assert fresh['scenes'][0]['chapters'][1]['guidance']['continuityFromPrev'] is None
    assert store.job(j['id'])['result']==result


def test_legacy_default_does_not_override_analysis_and_manual_is_explicit(client,plan):
    pid=setup(client,plan)
    store.put_setting('delivery:'+pid,{'revision':0,'continuity_enabled':True,'context_frames':22,'scenes':{'scene':{'chapters':{'shot2':{'guide_from_previous':True}}}}})
    p=client.get('/api/projects/'+pid).json()
    assert p['delivery']['scenes'][0]['chapters'][1]['guidance']['continuityFromPrev'] is None
    j,result=review(client,pid);client.post('/api/jobs/'+j['id']+'/manual',json=result)
    p=client.get('/api/projects/'+pid).json();cfg=p['delivery']['configuration'];cfg['production_revision']=p['revision'];cfg['scenes']['scene']['chapters']['shot2']['guidance_mode']='manual'
    client.put('/api/projects/'+pid+'/delivery',json=cfg)
    g=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]['chapters'][1]['guidance']
    assert g['manual'] and g['continuityFromPrev'] and not g['recommended']
    cfg=client.get('/api/projects/'+pid).json()['delivery']['configuration'];cfg['production_revision']=p['revision'];cfg['continuity_enabled']=False
    client.put('/api/projects/'+pid+'/delivery',json=cfg)
    g=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]['chapters'][1]['guidance']
    assert g['continuityFromPrev'] is True and g['enabled'] is False


def test_validator_rejects_missing_wrong_previous_fabricated_evidence(client,plan):
    pid=setup(client,plan);j,result=review(client,pid);source=store.job(j['id'])['input']['guidance_source']
    for change in ['missing','previous','evidence','first']:
        r=copy.deepcopy(result)
        if change=='missing':r['decisions'].pop()
        elif change=='previous':r['decisions'][1]['previous_shot_id']='someone_else'
        elif change=='evidence':r['decisions'][1]['evidence']=['invented camera direction']
        else:r['decisions'][0]['decision']='extend'
        with pytest.raises(ValueError):guidance.validate(r,source)
    assert providers.result_model('h3_guidance')==models.ShotGuidanceReview


@pytest.mark.parametrize('decision,expected',[('extend',True),('uncertain',None)])
def test_extend_and_uncertain_are_distinct_from_off(client,plan,decision,expected):
    pid=setup(client,plan);j,result=review(client,pid,decision)
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    g=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]['chapters'][1]['guidance']
    assert g['continuityFromPrev'] is expected
    # A changed prior shot invalidates even a previously completed review.
    p=store.project(pid);p['production']['shots'][0]['camera']='Different camera path'
    client.put('/api/projects/'+pid+'/plan',json={'revision':p['revision'],'production':p['production']})
    assert client.get('/api/projects/'+pid).json()['delivery']['guidance_review']['status']=='pending'


def test_read_only_state_never_enqueues_and_empty_project_rejected(client,plan):
    empty=client.post('/api/projects',json={'title':'Empty','idea':'Create a film'}).json()['id']
    assert client.post('/api/projects/'+empty+'/guidance/analyze').status_code==400
    pid=setup(client,plan)
    for _ in range(2):assert client.get('/api/projects/'+pid).json()['delivery']['guidance_review']['status']=='pending'
    assert not [j for j in store.jobs(pid) if j['capability']=='h3_guidance']


def test_unprepared_scenes_do_not_block_real_analysis_or_fake_running_state(client,plan):
    pid=setup(client,plan);p=client.get('/api/projects/'+pid).json()
    assert any(s['preparation']['required'] for s in p['delivery']['scenes'])
    assert p['delivery']['guidance_review']['status']=='pending'
    assert '尚未啟動' in p['delivery']['scenes'][0]['chapters'][1]['guidance']['reason']
    j,result=review(client,pid)
    assert j['input']['guidance_source']['scenes'][0]['preparation_required']
    assert client.post('/api/jobs/'+j['id']+'/manual',json=result).status_code==200
    p=client.get('/api/projects/'+pid).json()
    assert p['delivery']['guidance_review']['status']=='ready'
    assert p['delivery']['scenes'][0]['chapters'][1]['guidance']['decision']=='cut'
    assert any(s['preparation']['required'] for s in p['delivery']['scenes'])


def test_older_running_analysis_is_explicit_and_fresh_analysis_starts_after_it_finishes(client,plan):
    pid=setup(client,plan);j,result=review(client,pid)
    with store.db() as c:c.execute("update jobs set state='running' where id=?",(j['id'],))
    cfg=client.get('/api/projects/'+pid).json()['delivery']['configuration'];cfg['production_revision']=1
    cfg['scenes']={'scene':{'chapters':{'shot2':{'shot_prompt':'New framing.'}}}}
    assert client.put('/api/projects/'+pid+'/delivery',json=cfg).status_code==200
    p=client.get('/api/projects/'+pid).json();review_state=p['delivery']['guidance_review']
    assert review_state['status']=='waiting' and review_state['job_id']==j['id']
    assert '上一個版本' in p['delivery']['scenes'][0]['chapters'][1]['guidance']['reason']
    assert client.post('/api/projects/'+pid+'/guidance/analyze').json()['status']=='waiting'
    with store.db() as c:c.execute("update jobs set state='succeeded',result=? where id=?",(store.encode(result),j['id']))
    assert client.get('/api/projects/'+pid).json()['delivery']['guidance_review']['status']=='pending'
    fresh=client.post('/api/projects/'+pid+'/guidance/analyze').json()['job']
    assert fresh['id']!=j['id'] and fresh['input']['guidance_hash']!=j['input']['guidance_hash']


def test_failed_analysis_exposes_error_without_claiming_it_is_running(client,plan):
    pid=setup(client,plan);j,result=review(client,pid)
    with store.db() as c:c.execute("update jobs set state='failed',error='Provider unavailable' where id=?",(j['id'],))
    p=client.get('/api/projects/'+pid).json();review_state=p['delivery']['guidance_review']
    assert review_state['status']=='failed' and review_state['error']=='Provider unavailable'
    assert '請查看原因' in p['delivery']['scenes'][0]['chapters'][1]['guidance']['reason']
