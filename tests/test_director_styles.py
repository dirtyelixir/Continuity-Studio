from test_directing import directed,reviewed,check_proposal
import copy
import json
import io
import zipfile
import pytest
from studio import store,engine,models,providers,director_styles
from test_production import client,plan,create


def result():
    return {'story_reading':'開燈帶來希望。','candidates':[{'style_id':i,'fit_reason':'用視線引導觀眾留意開關。','source_evidence':['A keeper fixes a lamp'],'approach':{'camera':'穩定中景','blocking':'手移向開關','editing':'開燈後保留停頓','lighting_color':'由暗至暖','keyframe_example':'手仍在開關前的瞬間'},'tradeoff':'保留動作清晰度。'} for i in ('spielberg','hou_hsiao_hsien','coen_brothers')]}


def recommend(client,pid):
    client.post('/api/settings/routing',json={'capability':'director_style','provider_id':'manual'})
    r=client.post(f'/api/projects/{pid}/jobs',json={'capability':'director_style'})
    assert r.status_code==200,r.text
    j=r.json()['job']
    r=client.post(f'/api/jobs/{j["id"]}/manual',json=result())
    assert r.status_code==200,r.text
    return j


def select(client,pid,j,style='spielberg',revision=1):
    return client.post(f'/api/projects/{pid}/director-style',json={'job_id':j['id'],'style_id':style,'revision':revision})


def test_catalog_complete_and_source_guard():
    catalog,meta=director_styles.library()
    assert len(catalog)==20 and meta['license']=='MIT'
    source={'idea':'A keeper fixes a lamp','production':None}
    director_styles.validate(result(),source)
    for alteration in ('unknown','duplicate','quote'):
        r=result()
        if alteration=='unknown':r['candidates'][0]['style_id']='nonexistent'
        if alteration=='duplicate':r['candidates'][0]['style_id']='coen_brothers'
        if alteration=='quote':r['candidates'][0]['source_evidence']=['An invented scene']
        with pytest.raises(ValueError):director_styles.validate(r,source)


def test_selection_frozen_prompt_and_adoption(client,plan):
    pid=create(client,plan);before=store.project(pid)
    j=recommend(client,pid)
    assert '20' in j['input']['prompt'] and 'style_id' in j['input']['prompt']
    assert select(client,pid,j).status_code==200
    assert store.project(pid)==before  # Choosing a lens never edits canonical production.
    p=client.get(f'/api/projects/{pid}').json()
    assert p['director_styles']['recommendation']['id']==j['id']
    assert p['director_styles']['selected']['style_id']=='spielberg'
    inp,_=engine.build_input(before,models.JobRequest(capability='narrative'))
    assert director_styles.library()[0]['spielberg']['content'] in inp['prompt']
    assert director_styles.library()[0]['hou_hsiao_hsien']['content'] not in inp['prompt']
    assert inp['director_selection']['style_id']=='spielberg'
    client.post('/api/settings/routing',json={'capability':'narrative','provider_id':'manual'})
    nj=client.post(f'/api/projects/{pid}/jobs',json={'capability':'narrative'}).json()['job']
    assert client.post(f'/api/jobs/{nj["id"]}/manual',json=directed(plan)).status_code==200
    assert client.get(f'/api/projects/{pid}').json()['director_styles']['applied'] is None
    client.post('/api/settings/routing',json={'capability':'directing_qc','provider_id':'manual'})
    check_proposal(client,{'id':pid},nj,reviewed(directed(plan)))
    assert select(client,pid,j,'coen_brothers').status_code==200
    assert client.post(f'/api/jobs/{nj["id"]}/adopt',json={'revision':1}).status_code==400
    assert select(client,pid,j).status_code==200
    assert client.post(f'/api/jobs/{nj["id"]}/adopt',json={'revision':1}).status_code==200
    state=client.get(f'/api/projects/{pid}').json()['director_styles']
    assert state['applied']['style_id']=='spielberg' and state['recommendation'] is None
    assert select(client,pid,j,revision=2).status_code==400
    assert client.post(f'/api/projects/{pid}/director-style',json={'revision':2}).status_code==200
    assert director_styles.selection(pid) is None


def test_cross_project_and_invalid_selection(client,plan):
    pid=create(client,plan);j=recommend(client,pid);other=create(client,plan)
    assert select(client,other,j).status_code==400
    assert select(client,pid,j,'nolan').status_code==400
    assert select(client,pid,j,revision=0).status_code==400


def test_manual_invalid_evidence_rejected_and_can_resubmit(client,plan):
    pid=create(client,plan)
    client.post('/api/settings/routing',json={'capability':'director_style','provider_id':'manual'})
    j=client.post(f'/api/projects/{pid}/jobs',json={'capability':'director_style'}).json()['job']
    r=result();r['candidates'][0]['source_evidence']=['invented']
    assert client.post(f'/api/jobs/{j["id"]}/manual',json=r).status_code==400
    assert client.post(f'/api/jobs/{j["id"]}/manual',json=result()).status_code==200


def test_storyboard_gets_selected_lens_without_changing_source(client,plan):
    pid=client.post('/api/projects',json={'title':'source','idea':'A keeper fixes a lamp','source_kind':'story','style':'Stop-motion, 16:9'}).json()['id']
    j=recommend(client,pid)
    assert select(client,pid,j,revision=0).status_code==200
    inp,_=engine.build_input(store.project(pid),models.JobRequest(capability='storyboard'))
    assert inp['source']['source_text']=='A keeper fixes a lamp'
    assert 'Stop-motion, 16:9' in inp['prompt']
    assert inp['director_selection']['style_id']=='spielberg'
    assert '4–15' in inp['prompt'] and 'reveal order' in inp['prompt']


def test_capability_defaults_to_astra(client):
    assert providers.resolve('director_style')['id']=='astra'
    assert providers.result_model('director_style') is models.DirectorRecommendations


def test_export_records_applied_and_pending_choice(client,plan):
    pid=create(client,plan);j=recommend(client,pid)
    assert select(client,pid,j).status_code==200
    response=client.get(f'/api/projects/{pid}/export')
    assert response.status_code==200,response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        d=json.loads(z.read('director-style.json'))
    assert d['selected']['style_id']=='spielberg'
    assert d['applied'] is None


def test_inflight_different_direction_cannot_be_misreported_as_new_job(client,plan):
    pid=create(client,plan);j=recommend(client,pid)
    select(client,pid,j)
    client.post('/api/settings/routing',json={'capability':'narrative','provider_id':'manual'})
    first=client.post(f'/api/projects/{pid}/jobs',json={'capability':'narrative'})
    assert first.status_code==200
    select(client,pid,j,'coen_brothers')
    later=client.post(f'/api/projects/{pid}/jobs',json={'capability':'narrative'})
    assert later.status_code==400 and '導演方向' in later.text
