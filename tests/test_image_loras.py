import copy
import json
import shutil
import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from studio import image_loras as lora, local_images as local, engine, store, models, providers
from test_production import client, plan, create
from test_image_prompt_assembly import prepared


def fixture(recipe='krea_new'):
    count=0 if recipe=='krea_new' else 1
    p=local.select({'image_source':{'target_kind':'prop'},'images':[],'image_reference_roles':[]})
    p.update(recipe=recipe,reference_count=count)
    family,model=lora.model_for(p)
    context={'version':lora.VERSION,'family':family,'model':model,'recipe':recipe,
             'candidates':[{'id':'sample','name':'sub/sample.safetensors','strength':0.6,
                            'trigger':'ink wash style','family':family,'description':'ink','sources':['test fixture']}], 'excluded':[]}
    brief=prepared('room');brief['visual_style']='An ink wash style illustration.'
    selection={'summary':'配合水墨要求。','selected':[{'id':'sample','reason':'水墨畫。','evidence':['ink wash style']}]}
    return p,context,brief,selection


@pytest.mark.parametrize('recipe',['krea_new','krea_edit','krea_two','krea_inpaint','krea_outpaint','klein_reference','klein_portrait','klein_face','klein_sheet'])
def test_graph_routes_selected_adapters_and_preserves_functional_chain(recipe):
    p,c,b,s=fixture(recipe)
    p.update(region=[20,20,40,40],padding=[64,0,64,0])
    g=local.build(lora.apply(p,s,c,b),'Photographic still.', ['ref.png']*(2 if recipe in ('krea_two','klein_face') else p['reference_count']),'test')
    prefixes=['p0_','p1_','p2_','p3_'] if recipe=='klein_sheet' else ['']
    for pre in prefixes:
        node=g[pre+'creative_lora_0']
        assert node['inputs']['lora_name']=='sub/sample.safetensors'
        assert node['inputs']['strength_model']==0.6
        if recipe.startswith('klein'):
            assert g[pre+'attention']['inputs']['model']==[pre+'creative_lora_0',0]
            assert node['inputs']['model']==[pre+('face_lora' if recipe=='klein_face' else 'turbo'),0]
            assert g[pre+'turbo']['inputs']['strength_model']==0.2
        elif recipe=='krea_new':assert g['samples']['inputs']['model']==['creative_lora_0',0]
        else:
            assert node['inputs']['model']==['edit_lora',0]
            assert g['edit_patch']['inputs']['model']==['creative_lora_0',0]
        text=g[pre+'positive']['inputs'].get('text',g[pre+'positive']['inputs'].get('prompt'))
        assert text.startswith('ink wash style\n\n')
    assert sum(n['class_type']=='SaveImage' for n in g.values())==1


def test_none_keeps_original_graph_and_trigger_dedup():
    p,c,b,s=fixture()
    empty={'summary':'無需額外 LoRA。','selected':[]}
    assert local.build(p,'brief',[],'t')==local.build(lora.apply(p,empty,c,b),'brief',[],'t')
    chosen=lora.apply(p,s,c,b)
    assert lora.prompt_with_triggers(chosen,'INK WASH STYLE portrait')=='INK WASH STYLE portrait'


@pytest.mark.parametrize('mutation',['unknown','duplicate','evidence','empty_evidence','nan','inf','bool','negative','path','absolute','family','model','recipe'])
def test_invalid_selection_never_reaches_graph(mutation):
    p,c,b,s=fixture()
    if mutation=='unknown':s['selected'][0]['id']='invented'
    if mutation=='duplicate':s['selected']*=2
    if mutation=='evidence':s['selected'][0]['evidence']=['not in the brief']
    if mutation=='empty_evidence':s['selected'][0]['evidence']=[' ']
    if mutation in ('nan','inf','bool','negative'):c['candidates'][0]['strength']={'nan':float('nan'),'inf':float('inf'),'bool':True,'negative':-1}[mutation]
    if mutation in ('path','absolute'):c['candidates'][0]['name']='../outside.safetensors' if mutation=='path' else '/outside.safetensors'
    if mutation=='family':c['family']='klein'
    if mutation=='model':c['model']='wrong.safetensors'
    if mutation=='recipe':c['recipe']='krea_edit'
    with pytest.raises(ValueError):lora.apply(p,s,c,b)


def test_frozen_plan_tampering_and_missing_lora_block():
    p,c,b,s=fixture();p=lora.apply(p,s,c,b)
    tampered=copy.deepcopy(p);tampered['creative_loras'][0]['strength']=1.5
    with pytest.raises(ValueError):local.build(tampered,'brief',[],'test')
    del tampered['lora_selection']
    with pytest.raises(ValueError):local.build(tampered,'brief',[],'test')
    info=json.loads((local.ROOT/'runtime-schemas.json').read_text())
    with pytest.raises(ValueError,match='sample.safetensors'):
        local.validate_graph(local.build(p,'brief',[],'test'),info)


def test_owned_catalog_relocation_and_eligibility(tmp_path,monkeypatch):
    catalog=tmp_path/'loras.json';shutil.copyfile(lora.CATALOG,catalog)
    monkeypatch.setattr(lora,'CATALOG',catalog)
    names=['Flux Krea 2/Krea2-realism-V2.safetensors','krea2_darkbrush.safetensors',
           'Krea-2/01-krea2_darkbrush.safetensors','f2k_9B_lcs_consist_20260415.safetensors',
           'Flux Krea 2/Krea2 NSFW+.safetensors','arbitrary-unknown.safetensors']
    info={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[names]}}}}
    p,*_=fixture();c=lora.snapshot(p,info)
    assert [x['id'] for x in c['candidates']]==['krea_darkbrush','krea_realism_v2']
    assert len(c['excluded'])==1
    p,*_=fixture('klein_reference');c=lora.snapshot(p,info)
    assert [x['id'] for x in c['candidates']]==['klein_consistency_9b']
    p['reference_count']=0
    assert not lora.snapshot(p,info)['candidates']


def setup_engine(client,plan,monkeypatch):
    from studio import comfy_images
    monkeypatch.setattr(comfy_images,'preflight',lambda work:None)  # Offline renderer fixture.
    pid=create(client,plan)
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    p,c,b,s=fixture()
    monkeypatch.setattr(lora,'snapshot',lambda p:copy.deepcopy(c))
    store.put_setting('routing',{'image_review':'manual'})
    calls=[]
    def run(provider,cap,prompt,images,work):
        calls.append((cap,copy.deepcopy(provider),prompt))
        if cap=='image_prepare':return {**b,'local_lora_selection':s}
        path=work/'fixture.png';Image.new('RGB',(256,256),'white').save(path)
        return {'image_path':str(path),'notes':'Test fixture; not generation.'}
    monkeypatch.setattr(providers,'run',run)
    return pid,c,calls


def test_engine_automatically_applies_and_freezes_selection(client,plan,monkeypatch):
    pid,ctx,calls=setup_engine(client,plan,monkeypatch)
    before=copy.deepcopy(store.project(pid))
    def generate():
        j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',image_provider='comfy_local',force=True))['job']
        engine.execute(j['id']);done=store.job(j['id'])
        assert done['state']=='succeeded',done['error']
        return done
    first=generate()
    assert 'LOCAL IMAGE LORA SELECTION' in calls[0][2]
    final=first['input']['provider_config']['local_plan']
    assert final==first['input']['local_image_plan'] and final['creative_loras'][0]['name']=='sub/sample.safetensors'
    assert calls[1][1]['local_plan']==final
    assert (store.DATA/'jobs'/first['id']/'image-lora-selection.json').exists()
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert json.loads(z.read('local-images/'+first['id']+'/selection.json'))==final
        assert json.loads(z.read('local-images/'+first['id']+'/image-lora-selection.json'))['selection']==final['lora_selection']
    second=generate()
    assert second['input']['image_preparation_origin']['mode']=='reused'
    assert [x[0] for x in calls]==['image_prepare','image','image']
    ctx['candidates'][0]['description']='Changed reviewed metadata'
    third=generate()
    assert third['input']['image_preparation_origin']['mode']=='prepared'
    assert [x[0] for x in calls].count('image_prepare')==2
    assert store.project(pid)==before


def test_missing_decision_fails_before_media(client,plan,monkeypatch):
    pid,c,calls=setup_engine(client,plan,monkeypatch)
    def missing(provider,cap,prompt,images,work):
        assert cap=='image_prepare'
        return prepared('room')
    monkeypatch.setattr(providers,'run',missing)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',image_provider='comfy_local'))['job']
    engine.execute(j['id'])
    assert store.job(j['id'])['state']=='failed'
    assert not store.assets(pid)


def test_unavailable_catalog_and_candidate_family_errors():
    p,c,b,s=fixture()
    for info in ({},{'LoraLoaderModelOnly':{'input':{'required':{'lora_name':['invalid']}}}}):
        with pytest.raises(ValueError,match='清單'):lora.snapshot(p,info)
    c['candidates'][0]['family']='klein'
    with pytest.raises(ValueError,match='底模'):lora.apply(p,s,c,b)


def test_surplus_invalid_quotes_are_removed_without_rewriting_choice_or_brief():
    p,c,b,s=fixture();s['selected'][0]['evidence'] += ['Keep all reference designs.',' ']
    original=copy.deepcopy((b,s,c,p))
    grounded,audit=lora.grounded_selection(s,c,b)
    assert grounded['selected'][0]['evidence']==['ink wash style']
    assert [(r['id'],r['quote']) for r in audit['discarded']]==[('sample','Keep all reference designs.'),('sample',' ')]
    assert audit['original']==s and audit['selection']==grounded
    assert (b,s,c,p)==original
    assert lora.apply(p,grounded,c,b)['creative_loras'][0]['strength']==0.6
    with pytest.raises(ValueError,match=lora.EVIDENCE_ERROR):lora.apply(p,s,c,b)


def test_every_selected_adapter_requires_its_own_grounded_quote():
    p,c,b,s=fixture()
    c['candidates'].append({**c['candidates'][0],'id':'second'})
    s['selected'].append({'id':'second','reason':'Another effect','evidence':['absent']})
    with pytest.raises(ValueError,match=lora.EVIDENCE_ERROR):lora.grounded_selection(s,c,b)
    s['selected'][1]['id']='unknown'
    with pytest.raises(ValueError,match='未知'):lora.grounded_selection(s,c,b)


def failed_citation_job(client,plan,monkeypatch):
    pid,ctx,calls=setup_engine(client,plan,monkeypatch)
    original_run=providers.run
    def run(provider,cap,prompt,images,work):
        result=original_run(provider,cap,prompt,images,work)
        if cap=='image_prepare':result['local_lora_selection']['selected'][0]['evidence'].insert(0,'Preserve matching design and composition; correct only requested issues.')
        return result
    monkeypatch.setattr(providers,'run',run)
    req=models.JobRequest(capability='image',target_id='room',image_provider='comfy_local',force=True)
    job=engine.enqueue(pid,req)['job']
    with monkeypatch.context() as old:
        def strict(selection,context,brief):
            return lora.validate(selection,context,brief),{}
        old.setattr(lora,'grounded_selection',strict)
        engine.execute(job['id'])
    job=store.job(job['id'])
    assert job['state']=='failed' and job['error']==lora.EVIDENCE_ERROR
    assert [x[0] for x in calls]==['image_prepare']
    return pid,req,job,calls


def test_explicit_retry_reuses_original_failed_brief_with_audited_evidence(client,plan,monkeypatch):
    pid,req,old,calls=failed_citation_job(client,plan,monkeypatch)
    work=store.DATA/'jobs'/old['id']
    before={str(p):p.read_bytes() for p in work.rglob('*') if p.is_file()}
    job=engine.enqueue(pid,req)['job'];engine.execute(job['id']);done=store.job(job['id'])
    assert done['state']=='succeeded',done['error']
    assert [x[0] for x in calls]==['image_prepare','image']
    assert done['input']['image_preparation_origin']['original_job_id']==old['id']
    assert done['input']['image_preparation_origin']['stage']=='saved-before-lora-validation'
    audit=json.loads((store.DATA/'jobs'/job['id']/'image-lora-evidence.json').read_text())
    assert len(audit['discarded'])==1
    assert audit['selection']['selected'][0]['evidence']==['ink wash style']
    assert done['input']['image_preparation']['local_lora_selection']==audit['selection']
    assert done['input']['image_prompt']==(work/'preparation/render-prompt.txt').read_text()
    assert before=={str(p):p.read_bytes() for p in work.rglob('*') if p.is_file()}
    assert store.job(old['id'])==old
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert json.loads(z.read('local-images/'+job['id']+'/image-lora-evidence.json'))==audit


@pytest.mark.parametrize('change',['request','source','render','manifest','result','cancel','receipt','fingerprint'])
def test_failed_checkpoint_mismatch_cannot_be_reused(client,plan,monkeypatch,change):
    from studio import image_prompts
    pid,req,old,calls=failed_citation_job(client,plan,monkeypatch)
    fingerprint=image_prompts.preparation_fingerprint(old['input'],[])
    work=store.DATA/'jobs'/old['id'];prep=work/'preparation'
    assert image_prompts.saved_lora_failure(old,fingerprint) is not None
    if change in ('request','source','render'):
        path=prep/{'request':'request.txt','source':'source.json','render':'render-prompt.txt'}[change]
        path.write_text(path.read_text()+' changed')
    elif change=='manifest':(prep/'inputs/reference-inputs.json').write_text('[{}]')
    elif change=='result':
        r=json.loads((prep/'result.json').read_text());r['local_lora_selection']['selected'][0]['evidence']=['absent']
        (prep/'result.json').write_text(json.dumps(r))
    elif change=='cancel':(work/'cancel-requested').touch()
    elif change=='receipt':(work/'comfy-receipt.json').write_text('{}')
    else:fingerprint='different-request'
    assert image_prompts.saved_lora_failure(old,fingerprint) is None
    assert [x[0] for x in calls]==['image_prepare']
