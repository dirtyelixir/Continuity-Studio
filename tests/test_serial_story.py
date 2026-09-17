import copy
import io
import zipfile
import pytest
from studio import store,engine,serial_story,continuity
from test_production import client,plan,add_asset
from test_directing import directed,reviewed,check_proposal


def setup(client):
    p=client.post('/api/projects',json={'title':'連載故事','idea':'Ada 逐章修復島上的燈，長線尋找失蹤的父親。','source_kind':'outline','style':'2D 動畫；16:9'}).json()
    client.post('/api/settings/routing',json={'capability':'narrative','provider_id':'manual'})
    return p


def draft(client,p,title='第一章',kind='idea'):
    r=client.post('/api/projects/'+p['id']+'/chapters',json={'title':title,'brief':'Ada 在工作室修復第一盞燈。','source_kind':kind})
    assert r.status_code==200,r.text
    return r.json()


def candidate(client,p,ch,plan):
    plan=directed(plan)
    r=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'narrative','target_id':ch['id']})
    assert r.status_code==200,r.text
    j=r.json()['job']
    r=client.post('/api/jobs/'+j['id']+'/manual',json=plan)
    assert r.status_code==200,r.text
    return j


def adopt(client,j,revision):
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'manual'})
    saved=store.job(j['id']);prod=saved['result'].get('production',saved['result'])
    check_proposal(client,{'id':j['project_id']},j,reviewed(prod))
    r=client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':revision})
    assert r.status_code==200,r.text
    return r.json()


def test_outline_is_persistent_and_never_runs_as_short_story(client):
    p=setup(client)
    assert not store.jobs(p['id'])
    for cap in ['narrative','storyboard']:
        assert client.post('/api/projects/'+p['id']+'/jobs',json={'capability':cap}).status_code==400
    one=draft(client,p);two=draft(client,p,'第二章')
    state=client.get('/api/projects/'+p['id']).json()
    assert [c['id'] for c in state['story_chapters']]==[one['id'],two['id']]
    assert state['idea']==p['idea'] and state['style']=='2D 動畫；16:9'
    assert state['production'] is None


def test_two_chapters_reuse_canon_keep_assets_and_revision_is_scoped(client,plan):
    p=setup(client);one=draft(client,p)
    j=candidate(client,p,one,plan)
    assert j['input']['serial_source']['outline']==p['idea']
    assert 'Develop ONLY the selected story chapter' in j['input']['prompt']
    first=adopt(client,j,0);original=copy.deepcopy(first['production'])
    a=add_asset(p['id'],original,'ada')
    f=add_asset(p['id'],original,original['shots'][0]['keyframes'][0]['id'])
    two=draft(client,p,'第二章');p2=copy.deepcopy(plan);p2['story']='Ada 找到下一條線索。';p2['screenplay']='ADA: Another clue.'
    j2=candidate(client,p,two,p2)
    assert 'Three coat buttons' in j2['input']['prompt'] and plan['screenplay'] in j2['input']['prompt']
    second=adopt(client,j2,1);prod=second['production']
    assert second['title']==p['title'] and second['idea']==p['idea']
    assert len(prod['chapters'])==2 and len(prod['canon'])==2
    assert prod['scenes'][0]==original['scenes'][0] and prod['shots'][0]==original['shots'][0]
    assert all(x['status']=='approved' for x in store.assets(p['id']))
    assert continuity.target_hash(prod,original['shots'][0]['keyframes'][0]['id'])==continuity.target_hash(original,original['shots'][0]['keyframes'][0]['id'])
    later=copy.deepcopy(prod['shots'][1]);changed=copy.deepcopy(plan);changed['shots'][0]['title']='修訂第一章';changed['story']='只修訂第一章。'
    revised=adopt(client,candidate(client,p,one,changed),2)['production']
    assert revised['shots'][1]==later and revised['chapters'][1]==prod['chapters'][1]
    assert revised['shots'][0]['id']==original['shots'][0]['id']
    assert len(revised['shots'])==2 and len(revised['chapters'])==2
    # Revision snapshots carry chapter ownership and each chapter's writing.
    restored=client.post('/api/projects/'+p['id']+'/restore/2',json={'revision':3})
    assert restored.status_code==200 and restored.json()['production']==prod
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+p['id']+'/export').content)) as z:
        assert z.read('story/outline.txt').decode()==p['idea']
        assert z.read('story/chapters/'+two['id']+'/screenplay.txt').decode()==p2['screenplay']


@pytest.mark.parametrize('change',['outline','chapter','production'])
def test_stale_chapter_proposals_cannot_overwrite_newer_work(client,plan,change):
    p=setup(client);ch=draft(client,p);j=candidate(client,p,ch,plan)
    if change=='outline':
        r=client.put('/api/projects/'+p['id']+'/outline',json={'idea':'更新後的長線大綱。','brief_revision':0})
        assert r.status_code==200
        assert client.put('/api/projects/'+p['id']+'/outline',json={'idea':'過期的大綱。','brief_revision':0}).status_code==400
    elif change=='chapter':
        data={'title':ch['title'],'brief':'本章已改變的事件。','version':0}
        assert client.put('/api/projects/'+p['id']+'/chapters/'+ch['id'],json=data).status_code==200
        assert client.put('/api/projects/'+p['id']+'/chapters/'+ch['id'],json=data).status_code==400
    else: engine.save_plan(p['id'],plan,0,'Newer edit')
    before=store.project(p['id'])
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':0}).status_code==400
    assert store.project(p['id'])==before


def test_reject_canonical_redefinition_and_cross_project_chapter(client,plan):
    p=setup(client);ch=draft(client,p);adopt(client,candidate(client,p,ch,plan),0)
    second=draft(client,p,'第二章');changed=copy.deepcopy(plan);changed['canon'][0]['description']='Different person'
    j=candidate(client,p,second,changed)
    assert client.post('/api/jobs/'+j['id']+'/adopt',json={'revision':1}).status_code==400
    other=setup(client)
    assert client.post('/api/projects/'+other['id']+'/jobs',json={'capability':'narrative','target_id':ch['id']}).status_code==400


def test_chapter_screenplay_keeps_exact_original(client,plan):
    p=setup(client);ch=draft(client,p,kind='screenplay')
    client.post('/api/settings/routing',json={'capability':'storyboard','provider_id':'manual'})
    j=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'storyboard','target_id':ch['id']}).json()['job']
    assert j['input']['source']['source_text']==ch['brief']
    result=directed(plan);result['screenplay']=ch['brief']
    r=client.post('/api/jobs/'+j['id']+'/manual',json={'production':result,'coverage':[{'source_id':'P001','shot_ids':['shot'],'treatment':'本章完整呈現。'}],'adaptation_notes':[]})
    assert r.status_code==200,r.text
    adopted=adopt(client,j,0)
    assert adopted['production']['chapters'][0]['screenplay']==ch['brief']
    assert adopted['idea']==p['idea']


def test_story_can_grow_beyond_single_chapter_shot_limit(client,plan):
    p=setup(client);expanded=copy.deepcopy(plan);expanded['shots']=[]
    for i in range(21):
        shot=copy.deepcopy(plan['shots'][0]);shot['id']='shot_'+str(i)
        for f in shot['keyframes']: f['id']=f['id']+'_'+str(i)
        expanded['shots'].append(shot)
    one=draft(client,p);adopt(client,candidate(client,p,one,expanded),0)
    two=draft(client,p,'第二章');result=adopt(client,candidate(client,p,two,expanded),1)
    assert len(result['production']['shots'])==42 and len(result['production']['chapters'])==2
