"""Offline proof of shared production methods and provider-independent prompt reuse."""
import copy
import io
import json
import shutil
import zipfile

import httpx
import pytest
from PIL import Image

from studio import engine, image_prompts, models, production_methods, providers, skills, store, storyboarding
from test_production import client, plan, create, add_asset
from test_image_prompt_assembly import prepared
from test_storyboarding import imported, proposal


def install_skill(name, caps, text):
    source=store.DATA/'test-skills'/name
    source.mkdir(parents=True)
    (source/'SKILL.md').write_text(f'---\nname: {name}\ndescription: Isolated test instruction\n---\n'+text)
    (source/'studio.json').write_text(json.dumps({'id':name,'version':'1.0.0','capabilities':caps,'permissions':['project:read']}))
    installed=skills.install(str(source),str(store.DATA/'skills'))
    skills.set_enabled(str(store.DATA/'skills'),installed['id'],True,['project:read'])


def test_owned_bundle_relocates_and_corruption_blocks(tmp_path,monkeypatch):
    original=production_methods.status()
    bundle=tmp_path/'standalone-studio'/'methods'
    shutil.copytree(production_methods.ROOT,bundle)
    monkeypatch.setattr(production_methods,'ROOT',bundle)
    assert production_methods.status()==original
    for cap in providers.BUILTINS:
        text,meta=production_methods.snapshot(cap)
        assert meta['mandatory'] and text
        assert set(meta['instruction_files']).issubset(meta['files'])
    (bundle/'references/image-craft.md').write_text('Changed outside the version manifest')
    with pytest.raises(ValueError,match='固定版本'):
        production_methods.snapshot('image_prepare')


def test_same_preparation_rules_reach_both_providers_and_extensions_once(client,plan,monkeypatch,tmp_path):
    pid=create(client,plan)
    install_skill('prep-only',['image_prepare'],'PREP_ONLY_TEST_MARKER')
    install_skill('both',['image','image_prepare'],'BOTH_STAGES_TEST_MARKER')
    install_skill('wild',['*'],'WILDCARD_TEST_MARKER')
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    client.post('/api/settings/profile',json={'mode':'astra','image_provider':'comfy_local'})
    request=models.JobRequest(capability='image',target_id='room',force=True)
    first=engine.build_input(store.project(pid),request)[0]
    client.post('/api/settings/profile',json={'mode':'deepseek','image_provider':'comfy_local'})
    second=engine.build_input(store.project(pid),request)[0]
    assert first['prompt']==second['prompt'] and first['production_method']==second['production_method']
    for mark in ('PREP_ONLY_TEST_MARKER','BOTH_STAGES_TEST_MARKER','WILDCARD_TEST_MARKER'):
        assert first['prompt'].count(mark)==1
    assert first['production_method']['mandatory']
    request_text=first['prompt'];observed=[]
    def codex(provider,cap,prompt,images,work):
        observed.append(prompt);return prepared()
    monkeypatch.setattr(providers,'codex_run',codex)
    providers.run(providers.DEFAULT,'image_prepare',request_text,[],tmp_path/'codex')
    real=httpx.Client
    def http_reply(req):
        observed.append(json.loads(req.content)['messages'][0]['content'])
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(prepared())},'finish_reason':'stop'}]})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(http_reply),**kw))
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-only')
    providers.run(providers.deepseek_provider(),'image_prepare',request_text,[],tmp_path/'deepseek')
    assert observed[0]==request_text and observed[1].startswith(request_text+'\nReturn JSON matching this schema:')


@pytest.mark.parametrize('kind',['character','crowd','prop','location','frame'])
def test_compiler_owns_constraints_not_model_fields(plan,kind):
    target='start' if kind=='frame' else 'ada'
    if kind!='frame':plan['canon'][0]['kind']=kind
    source=image_prompts.source(plan,target)
    result=prepared(target)
    # The model supplies only visual fields; it cannot delete mandatory rules.
    final=image_prompts.compile_prompt(result,source,'App-owned target layout',[])
    for rule in source['render_contract']['rules']:assert rule in final
    before=final
    old=copy.deepcopy(source)
    source['render_contract']['rules']=['Changed policy for a new job only']
    assert image_prompts.compile_prompt(result,old,'App-owned target layout',[])==before
    assert image_prompts.compile_prompt(result,source,'App-owned target layout',[])!=before


def setup_image_jobs(client,plan,monkeypatch):
    from studio import comfy_images
    monkeypatch.setattr(comfy_images,'preflight',lambda work:None)  # Offline renderer fixture.
    from studio import image_loras
    snapshot=image_loras.snapshot
    info={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[[]]}}}}
    monkeypatch.setattr(image_loras,'snapshot',lambda p:snapshot(p,info))
    pid=create(client,plan)
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    # Protocol-only Codex renderer fixture; no tool, model or GPU is invoked.
    store.put_setting('routing',{'image_review':'manual'})
    calls=[]
    def run(provider,cap,prompt,images,work):
        calls.append((provider['id'],cap,prompt))
        if cap=='image_prepare':
            return {**prepared('room'),'local_lora_selection':{'summary':'No compatible fixture adapters.','selected':[]} if 'LOCAL IMAGE LORA SELECTION' in prompt else None}
        assert cap=='image'
        output=work/'fixture.png';Image.new('RGB',(256,256),'blue').save(output)
        return {'image_path':str(output),'notes':'Isolated test fixture, not generated media'}
    monkeypatch.setattr(providers,'run',run)
    return pid,calls


def execute_image(pid,**kw):
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',force=True,**kw))['job']
    engine.execute(j['id'])
    done=store.job(j['id'])
    assert done['state']=='succeeded',done['error']
    return done


@pytest.mark.parametrize('renderer',['astra','comfy_local'])
def test_provider_switch_reuses_exact_prompt_without_calling_new_model(client,plan,monkeypatch,renderer):
    pid,calls=setup_image_jobs(client,plan,monkeypatch)
    store.put_setting('routing',{'image':renderer,'image_review':'manual'})
    before=copy.deepcopy(store.project(pid))
    first=execute_image(pid)
    store.put_setting('routing',{'image':renderer,'image_prepare':'deepseek','image_review':'manual'})
    second=execute_image(pid)
    assert [cap for _,cap,_ in calls]==['image_prepare','image','image']
    assert first['input']['image_prompt']==second['input']['image_prompt']
    assert second['input']['image_preparation_origin']['mode']=='reused'
    assert second['input']['image_preparation_origin']['provider']=='astra'
    assert second['input']['image_preparer_config']['id']=='deepseek'
    assert store.project(pid)==before
    assert all(a['status']=='pending' for a in store.assets(pid))
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        records=json.loads(z.read('production-methods/used-methods.json'))
        record=next(x for x in records if x['job_id']==second['id'])
        assert record['image_prompt']==second['input']['image_prompt']
        assert record['image_preparation_origin']['job_id']==first['id']


@pytest.mark.parametrize('change',['feedback','skill','pixels','source','roles'])
def test_changed_request_does_not_reuse_brief(client,plan,monkeypatch,change):
    pid,calls=setup_image_jobs(client,plan,monkeypatch)
    # One genuine file attachment in temporary storage, no production imagery.
    aid=add_asset(pid,plan,'room')
    first=execute_image(pid)
    args={}
    if change=='feedback':args['feedback']='Use a colder palette.'
    elif change=='skill':install_skill('new-prep-rule',['image_prepare'],'NEW_PREPARATION_INSTRUCTION')
    elif change=='pixels':Image.new('RGB',(256,256),'green').save(store.DATA/store.assets(pid)[-1]['path'])
    elif change=='source':
        updated=copy.deepcopy(plan);updated['canon'][1]['description']='Square window and a metal bench.'
        engine.save_plan(pid,updated,1,'test-only source change')
    elif change=='roles':args['source_asset_id']=aid
    second=execute_image(pid,**args)
    assert [cap for _,cap,_ in calls].count('image_prepare')==2
    assert first['input']['image_preparation_fingerprint']!=second['input']['image_preparation_fingerprint']


def test_failed_renderer_brief_survives_astra_outage(client,plan,monkeypatch):
    pid,calls=setup_image_jobs(client,plan,monkeypatch)
    normal=providers.run
    def failing(provider,cap,prompt,images,work):
        if cap=='image':raise RuntimeError('Test-only renderer unavailable')
        return normal(provider,cap,prompt,images,work)
    monkeypatch.setattr(providers,'run',failing)
    first=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room'))['job']
    engine.execute(first['id'])
    assert store.job(first['id'])['state']=='failed'
    store.put_setting('routing',{'image_prepare':'deepseek','image_review':'manual'})
    monkeypatch.setattr(providers,'run',normal)
    done=execute_image(pid)
    assert done['input']['image_preparation_origin']['job_id']==first['id']
    assert [cap for _,cap,_ in calls]==['image_prepare','image']


def test_deepseek_storyboard_has_bounded_saved_correction(client,plan,monkeypatch,tmp_path):
    p=imported(client)
    request,source,_=storyboarding.build(p,'')
    good=proposal(plan)
    bad={**good,'coverage':[]}
    outputs=iter([bad,good]);calls=[];real=httpx.Client
    def handler(req):
        calls.append(json.loads(req.content))
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(next(outputs))},'finish_reason':'stop'}]})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(providers,'codex_run',lambda *a:pytest.fail('No Astra fallback'))
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-only')
    result=storyboarding.run(providers.deepseek_provider(),request,[],tmp_path/'job',source)
    assert result==good and len(calls)==2
    assert json.loads((tmp_path/'job/result.json').read_text())==bad
    assert json.loads((tmp_path/'job/repair-1/result.json').read_text())==good
    assert 'ONE CORRECTION PASS' in calls[1]['messages'][0]['content']
