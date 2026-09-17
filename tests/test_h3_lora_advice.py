import copy
import pytest
from studio import engine, store, models, providers, h3_lora_advice as advice, h3_lora_catalog, h3_render_settings, video_render
from test_video_render import client, local, plan, schema

MOTION='camera_motion_h3_lora_v1_3000_pruned.safetensors'
REALISM='h3-realism-people-t2v-i2v-r2v.safetensors'

@pytest.fixture
def options(monkeypatch):
    from studio import comfy_video_provider
    result={'models':[{'name':n,'family':f} for f,n in h3_render_settings.DEFAULT_MODELS.items()],
            'loras':[dict(h3_lora_catalog.preset(n),name=n,family=None) for n in [MOTION,REALISM]]}
    monkeypatch.setattr(comfy_video_provider,'options',lambda:result)
    monkeypatch.setattr(engine.POOL,'submit',lambda *a,**kw:None)
    return result


def start(client,pid):
    response=client.post(f'/api/projects/{pid}/jobs',json={'capability':advice.CAPABILITY,'target_id':'shot','video_model':h3_render_settings.DEFAULT_MODELS['FL2VA']})
    assert response.status_code==200,response.text
    return response.json()['job']


def result_for(job,use=True):
    src=job['input']['lora_source']
    return {'summary':'建議只使用運鏡 LoRA。' if use else '本鏡不需要 Style LoRA。',
            'decisions':[{'name':c['name'],'use':use and c['name']==MOTION,'reason':'依本鏡已保存的鏡頭安排判斷。','evidence':[src['text'][:40]]} for c in src['candidates']]}


def test_job_provider_source_dedup_and_validated_apply(client,local,options):
    pid,remote=local;before=video_render.source(store.project(pid),'shot')
    job=start(client,pid)
    assert job['provider']==providers.resolve(advice.CAPABILITY)['id']
    assert job['input']['images']==[] and job['input']['production_method']['mandatory']
    assert start(client,pid)['id']==job['id']
    result=result_for(job);engine.finish(store.job(job['id']),result)
    state=client.get('/api/projects/'+pid).json()['video_renders']['shots']['shot']
    shown=state['style_lora_advice'][job['input']['lora_source']['model']]
    assert shown['state']=='succeeded' and shown['result']==result
    response=client.post(f'/api/projects/{pid}/video-workflow/shot/lora-advice-selection',json={'job_id':job['id'],'model':job['input']['lora_source']['model']})
    assert response.status_code==200,response.text
    assert response.json()['other_loras']==[{'name':MOTION,'strength':1.0}]
    assert video_render.source(store.project(pid),'shot')==before
    assert remote['posts']==0 and not video_render.state(store.project(pid))['takes']
    options['loras'][0]['default_strength']=.8
    with pytest.raises(ValueError,match='清單'):
        advice.selection(pid,'shot',job['input']['lora_source']['model'],job['id'])


def test_none_stale_wrong_model_and_bad_evidence(client,local,options,monkeypatch):
    pid,_=local;job=start(client,pid);basis=job['input']['lora_source']
    good=result_for(job,False)
    bad=copy.deepcopy(good);bad['decisions'][0]['evidence']=['invented source quote']
    with pytest.raises(ValueError,match='引用'):advice.validate(bad,basis)
    bad=copy.deepcopy(good);bad['decisions'][0]['name']='minimax_h3_turbo_4step.safetensors'
    with pytest.raises(ValueError,match='候選'):advice.validate(bad,basis)
    engine.finish(store.job(job['id']),good)
    assert advice.selection(pid,'shot',basis['model'],job['id'])==[]
    with pytest.raises(ValueError,match='更新'):advice.selection(pid,'shot',h3_render_settings.DEFAULT_MODELS['REF2VA'],job['id'])
    source=video_render.source(store.project(pid),'shot');source['text']+=' changed'
    monkeypatch.setattr(video_render,'source',lambda *a:source)
    with pytest.raises(ValueError,match='更新'):advice.selection(pid,'shot',basis['model'],job['id'])
