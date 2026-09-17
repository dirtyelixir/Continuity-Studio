import copy
import io
import json
import zipfile
import pytest
from studio import store,engine,models,providers,storyboarding
from test_production import client,plan
from test_directing import directed,reviewed,check_proposal

SOURCE='  夜。工作室。\nAda 按下開關。\nADA：Light.\n'

def imported(client,kind='screenplay'):
    r=client.post('/api/projects',json={'title':'匯入驗收','idea':SOURCE,'source_kind':kind,'source_filename':'劇本.txt'})
    assert r.status_code==200,r.text
    return r.json()

def proposal(plan,kind='screenplay'):
    p=directed(plan);p['screenplay' if kind=='screenplay' else 'story']=SOURCE
    return {'production':p,'coverage':[{'source_id':u['id'],'shot_ids':['shot'],'treatment':'由開燈鏡頭落實。'} for u in storyboarding.source_units(SOURCE)],'adaptation_notes':['測試資料，沒有實際生成圖片。']}

def manual(client,p):
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'manual'})
    client.post('/api/settings/routing',json={'capability':'storyboard','provider_id':'manual'})
    r=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'storyboard'})
    assert r.status_code==200,r.text
    return r.json()['job']

def test_import_preview_does_not_create_or_start_jobs(client):
    before=client.get('/api/projects').json()
    r=client.post('/api/story-import/preview',files={'file':('劇本.md',SOURCE.encode(),'text/markdown')})
    assert r.status_code==200,r.text
    assert r.json()['text']==SOURCE and len(r.json()['units'])==3
    assert client.get('/api/projects').json()==before
    assert client.post('/api/story-import/preview',files={'file':('bad.pdf',b'%PDF','application/pdf')}).status_code==400
    assert client.post('/api/story-import/preview',files={'file':('big.txt',b'a'*2000001)}).status_code==400

@pytest.mark.parametrize('kind',['story','screenplay'])
def test_source_to_adopt_to_existing_delivery_and_export(client,plan,kind):
    p=imported(client,kind);assert p['idea']==SOURCE and p['production'] is None
    assert store.jobs(p['id'])==[]
    j=manual(client,p);assert j['state']=='awaiting_input'
    assert j['input']['source']['source_text']==SOURCE
    assert j['input']['source']['reference_limit'] is None
    assert j['input']['skills'][0]['id']=='short-drama-storyboard'
    assert j['input']['skills'][0]['hash']
    assert '3–5 shots' not in j['input']['prompt']
    assert providers.resolve('narrative')['id']=='astra'
    result=proposal(plan,kind)
    r=client.post('/api/jobs/'+j['id']+'/manual',json=result);assert r.status_code==200,r.text
    assert store.project(p['id'])['production'] is None
    check_proposal(client,p,j,reviewed(result['production']))
    r=client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0});assert r.status_code==200,r.text
    current=client.get('/api/projects/'+p['id']).json()
    assert current['production']==result['production'] and current['idea']==SOURCE
    assert current['revision']==1 and len(current['delivery']['scenes'])==1
    assert current['assets']==[] and len(current['jobs'])==2
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+p['id']+'/export').content)) as z:
        assert z.read('source/original.txt').decode()==SOURCE
        assert 'P003' in z.read('source/storyboard-coverage.md').decode()
        assert json.loads(z.read('source/storyboard-skill.json'))[0]['id']=='short-drama-storyboard'
    # Changed production cannot export the old mapping as if it were current.
    changed=copy.deepcopy(result['production']);changed['shots'][0]['title']='修訂'
    engine.save_plan(p['id'],changed,1,'Test revision')
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+p['id']+'/export').content)) as z:
        assert 'source/storyboard-coverage.md' not in z.namelist()
        assert z.read('source/original.txt').decode()==SOURCE

@pytest.mark.parametrize('bad',['missing','duplicate','unknown_shot','unclaimed','changed_source','empty_treatment'])
def test_reject_invalid_provider_coverage_and_source(client,plan,bad):
    p=imported(client);j=manual(client,p);result=proposal(plan)
    if bad=='missing':result['coverage'].pop()
    if bad=='duplicate':result['coverage'][1]=result['coverage'][0]
    if bad=='unknown_shot':result['coverage'][0]['shot_ids']=['nonexistent']
    if bad=='unclaimed':
        shot=copy.deepcopy(plan['shots'][0]);shot['id']='extra'
        for f in shot['keyframes']:f['id']='extra_'+f['id']
        result['production']['shots'].append(shot)
    if bad=='changed_source':result['production']['screenplay']=SOURCE.strip()
    if bad=='empty_treatment':result['coverage'][0]['treatment']=' '
    r=client.post('/api/jobs/'+j['id']+'/manual',json=result)
    assert r.status_code==400,r.text
    assert store.project(p['id'])['production'] is None
    assert store.job(j['id'])['state']=='awaiting_input'

def test_stale_import_proposal_and_wrong_capability(client,plan):
    p=imported(client);j=manual(client,p)
    assert client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'narrative'}).status_code==400
    client.post('/api/jobs/'+j['id']+'/manual',json=proposal(plan))
    engine.save_plan(p['id'],plan,0,'Newer edit')
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==400
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':1}).status_code==400
    assert store.project(p['id'])['production']==plan

def test_legacy_projects_and_source_limits(client):
    old=client.post('/api/projects',json={'title':'Idea','idea':'Develop a story'}).json()
    assert old['source_kind']=='idea'
    assert client.post('/api/projects/'+old['id']+'/jobs',json={'capability':'storyboard'}).status_code==400
    for text in ['   ','x'*20001,'abc\x00def']:
        assert client.post('/api/projects',json={'title':'Invalid','idea':text,'source_kind':'story'}).status_code in [400,422]

def test_skill_bundle_is_pinned():
    text,meta=storyboarding.skill_instructions()
    assert 'Frozen Keyframe Craft' in text and '镜头设计方法' in text
    assert meta['license']=='MIT' and meta['adapter']=='studio-source-storyboard-v1'

def test_one_saved_candidate_repair_preserves_evidence(plan,tmp_path,monkeypatch):
    result=proposal(plan);bad=copy.deepcopy(result);bad['coverage'].pop()
    (tmp_path/'result.json').write_text(json.dumps(bad))
    calls=[]
    def run(provider,cap,prompt,images,work):
        calls.append((cap,prompt,images,work))
        assert 'ONE CORRECTION PASS' in prompt and 'P003' in prompt
        return result
    monkeypatch.setattr(providers,'run',run)
    source={'source_kind':'screenplay','source_text':SOURCE,'units':storyboarding.source_units(SOURCE)}
    assert storyboarding.run(providers.DEFAULT,'P003: source',[],tmp_path,source)==result
    assert len(calls)==1 and calls[0][3]==tmp_path/'repair-1' and calls[0][2]==[]
    assert json.loads((tmp_path/'result.json').read_text())==bad

def test_repair_is_bounded_and_transport_failures_do_not_retry(plan,tmp_path,monkeypatch):
    source={'source_kind':'screenplay','source_text':SOURCE,'units':storyboarding.source_units(SOURCE)}
    calls=[]
    def bad_result(provider,cap,prompt,images,work):
        calls.append(work);work.mkdir(parents=True,exist_ok=True)
        bad=proposal(plan);bad['coverage'].pop();(work/'result.json').write_text(json.dumps(bad))
        return bad
    monkeypatch.setattr(providers,'run',bad_result)
    with pytest.raises(ValueError):storyboarding.run(providers.DEFAULT,'source',[],tmp_path,source)
    assert len(calls)==2
    def unavailable(*args):
        calls.append('transport');raise RuntimeError('Transport failed')
    monkeypatch.setattr(providers,'run',unavailable)
    with pytest.raises(RuntimeError):storyboarding.run(providers.DEFAULT,'source',[],tmp_path/'other',source)
    assert calls.count('transport')==1

def test_reference_budget_for_default_image_provider(plan):
    result=proposal(plan);p=result['production']
    for i in range(4):
        p['canon'].append({'id':f'prop{i}','kind':'prop','name':'物件','description':'test','facts':[]})
        p['shots'][0]['entity_ids'].append(f'prop{i}')
    source={'source_kind':'screenplay','source_text':SOURCE,'units':storyboarding.source_units(SOURCE),'reference_limit':5}
    with pytest.raises(ValueError,match='參考圖'):storyboarding.validate(result,source)
    source['reference_limit']=None
    storyboarding.validate(result,source)


def test_many_short_lines_are_not_rejected_or_truncated(client):
    text='\n'.join('第 '+str(i)+' 句。' for i in range(350))
    preview=client.post('/api/story-import/preview',files={'file':('story.txt',text.encode())})
    assert preview.status_code==200 and preview.json()['text']==text
    assert len(preview.json()['units'])==350
    created=client.post('/api/projects',json={'title':'Long layout','idea':text,'source_kind':'story'})
    assert created.status_code==200 and store.project(created.json()['id'])['idea']==text
    assert not store.jobs(created.json()['id'])
