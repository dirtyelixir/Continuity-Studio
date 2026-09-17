import copy,hashlib,io,json
from contextlib import nullcontext
from pathlib import Path
import httpx
import pytest
from PIL import Image
from studio import local_images as local,comfy_images as comfy,store,engine,models,providers
from test_production import client,plan,create,add_asset

@pytest.fixture(autouse=True)
def offline_image_catalog(monkeypatch):
    from studio import image_loras
    real=image_loras.snapshot
    info={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[[]]}}}}
    monkeypatch.setattr(image_loras,'snapshot',lambda plan:real(plan,info))


def basis(kind='prop',count=0,source=False):
    return {'image_source':{'target_kind':kind},'images':['ref.png']*count,'image_reference_roles':['EDIT TARGET' if source and i==0 else 'identity' for i in range(count)],'source_asset_id':'source' if source else ''}

@pytest.mark.parametrize('kind,count,op,recipe',[('character',0,'auto','klein_sheet'),('character',2,'auto','klein_sheet'),('prop',0,'auto','krea_new'),('location',1,'auto','krea_edit'),('frame',2,'auto','klein_reference'),('frame',6,'auto','klein_reference'),('frame',1,'portrait','klein_portrait')])
def test_structural_routes(kind,count,op,recipe):
    assert local.select(basis(kind,count),op)['recipe']==recipe


def test_frame_canvas_follows_the_video_aspect_not_a_square():
    """A frame conditions a shot, so its canvas must match the aspect the video renders at."""
    from studio import h3_render_settings as render_settings
    expected=render_settings.dimensions(render_settings.defaults()['aspect_ratio'],local.FRAME_MEGAPIXELS)
    for count in (0,1,2,6):
        plan=local.select(basis('frame',count),'auto')
        assert (plan['width'],plan['height'])==expected,(count,plan['width'],plan['height'])
        assert plan['width']>plan['height'],'a frame canvas must stay landscape'
        assert plan['width']%32==0 and plan['height']%32==0,'latent canvas must be 32-aligned'
    # A frame canvas is the shot-aspect conditioning canvas whatever the recipe, including
    # an explicit portrait-style render; it is never left square or portrait-oriented.
    for op in ('auto','reference','portrait'):
        plan=local.select(basis('frame',1 if op!='reference' else 2),op)
        assert (plan['width'],plan['height'])==expected,(op,plan['width'],plan['height'])


def test_entity_and_character_canvases_are_unchanged_by_the_frame_rule():
    """Only frames follow the video aspect; identity and scene canvases keep their own sizes."""
    for kind,size in [('character',(2048,1152)),('prop',(1024,1024)),('location',(1024,1024))]:
        plan=local.select(basis(kind,0),'auto')
        assert (plan['width'],plan['height'])==size,(kind,plan['width'],plan['height'])


def test_invalid_inputs_never_silently_drop_images():
    for b,op in [(basis(count=9),'auto'),(basis(count=1),'new'),(basis(),'edit'),(basis('character',1),'portrait'),(basis(count=1),'face_swap')]:
        with pytest.raises(ValueError):local.select(b,op)


def test_graph_uses_all_references_and_only_one_save():
    p=local.select(basis('frame',6),'reference');g=local.build(p,'EXACT RENDER PROMPT',[f'ref{i}.png' for i in range(6)],'test')
    assert g['positive']['inputs']['text']=='EXACT RENDER PROMPT'
    assert len([n for n in g.values() if n['class_type']=='LoadImage'])==6
    assert len([n for n in g.values() if n['class_type']=='ReferenceLatent'])==12
    assert [n['class_type'] for n in g.values()].count('SaveImage')==1
    assert not any('Enhancer' in n['class_type'] or 'Preview' in n['class_type'] for n in g.values())


def test_mask_and_padding_preserve_unmodified_pixels(tmp_path):
    f=tmp_path/'source.png';Image.new('RGB',(1024,1024)).save(f)
    b=basis(count=1,source=True);b['images']=[str(f)]
    for op,region,pad in [('inpaint',[20,30,40,40],None),('outpaint',None,[128,0,128,0])]:
        p=local.select(b,op,region,pad);g=local.build(p,'modify',['source.png'],'test')
        assert g['save']['inputs']['images']==['composite',0]
        assert g['composite']['inputs']['mask']==(['mask',0] if region else ['pad',1])
        assert g['latent']['inputs']['width']==(1024 if region else 1280)
    with pytest.raises(ValueError):local.select(b,'inpaint',[90,20,30,20])
    with pytest.raises(ValueError):local.select(b,'outpaint',padding=[0,0,0,0])


def test_local_provider_profile_and_frozen_request(client,plan,monkeypatch):
    pid=create(client,plan);monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    assert client.post('/api/settings/profile',json={'mode':'astra','image_provider':'comfy_local'}).json()['mode']=='astra'
    assert providers.resolve('image')['kind']=='comfy'
    assert client.post('/api/settings/profile',json={'mode':'deepseek','image_provider':'comfy_local'}).json()['mode']=='deepseek'
    before=copy.deepcopy(store.project(pid))
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',image_provider='comfy_local'))['job']
    assert j['input']['local_image_plan']['recipe']=='krea_new'
    assert j['input']['provider_config']['local_plan']==j['input']['local_image_plan']
    assert engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',image_provider='comfy_local'))['job']['id']==j['id']
    with pytest.raises(ValueError):engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',image_provider='comfy_local',image_operation='reference'))
    assert store.project(pid)==before


def setup_transport(monkeypatch,tmp_path,*,lost=False,error=False,wrong=False):
    monkeypatch.setattr(comfy.comfy_runtime,'reserve',lambda mode:nullcontext({'mode':mode}))
    p=local.select(basis());prov={**local.PROVIDER,'local_plan':p};requests=[];state={'posted':False}
    output=io.BytesIO();Image.new('RGB',(1024,1024),'green').save(output,format='PNG');raw=output.getvalue()
    def handler(req):
        requests.append(req);path=req.url.path
        if path=='/vram/status':return httpx.Response(200,json={'ok':True,'monitor_alive':True})
        if path=='/object_info':return httpx.Response(200,json={})
        if path=='/prompt':
            state['posted']=True;state['payload']=json.loads(req.content)
            if lost:raise httpx.ReadTimeout('lost response',request=req)
            return httpx.Response(200,json={'prompt_id':'pid','node_errors':{}})
        hist={'prompt':[0,'pid',{}, {'studio_submission':state['payload']['extra_data']['studio_submission']}], 'status':{'completed':True,'status_str':'error' if error else 'success'},'outputs':{'other' if wrong else 'save':{'images':[{'filename':tmp_path.name+'_00001_.png','subfolder':'ContinuityStudio','type':'output'}]}}}
        if path=='/queue':return httpx.Response(200,json={'queue_running':[],'queue_pending':[]})
        if path in ('/history','/history/pid'):return httpx.Response(200,json={'pid':hist})
        if path=='/view':return httpx.Response(200,content=raw)
        raise AssertionError(path)
    real=httpx.Client;monkeypatch.setattr(comfy.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(local,'validate_graph',lambda *a:None)
    return prov,requests,raw


def test_submission_and_recovery_never_repost(monkeypatch,tmp_path):
    p,reqs,raw=setup_transport(monkeypatch,tmp_path,lost=True)
    with pytest.raises(RuntimeError,match='狀態未明'):comfy.run(p,'exact',[],tmp_path)
    monkeypatch.setattr(comfy.comfy_runtime,'reserve',lambda mode:pytest.fail('Recovery must not switch or reserve GPU'))
    result=comfy.run(p,'exact',[],tmp_path)
    assert Path(result['image_path']).read_bytes()==raw
    assert len([r for r in reqs if r.url.path=='/prompt'])==1
    assert json.loads((tmp_path/'comfy-receipt.json').read_text())['phase']=='render_complete'
    with pytest.raises(ValueError,match='不一致'):comfy.run(p,'changed',[],tmp_path)

@pytest.mark.parametrize('error,wrong',[(True,False),(False,True)])
def test_failure_and_wrong_output_fail_closed(monkeypatch,tmp_path,error,wrong):
    p,reqs,raw=setup_transport(monkeypatch,tmp_path,error=error,wrong=wrong)
    with pytest.raises((RuntimeError,ValueError)):comfy.run(p,'exact',[],tmp_path)
    assert not (tmp_path/'render.png').exists()
    assert len([r for r in reqs if r.url.path=='/prompt'])==1


def test_dependency_validation_blocks_before_submission():
    p=local.select(basis());graph=local.build(p,'x',[],'test')
    with pytest.raises(ValueError,match='UNETLoader'):local.validate_graph(graph,{})


def test_sheet_renders_four_distinct_views_with_shared_portrait():
    p=local.select(basis('character',1));g=local.build(p,'Visual style: photo\n\nAppearance: adult in green\n\nComposition: four panels\n\nLighting: soft',['layout.png'],'sheet')
    assert p['width']==2048 and p['height']==1152
    assert sum(n['class_type']=='SamplerCustomAdvanced' for n in g.values())==4
    assert sum(n['class_type']=='SaveImage' for n in g.values())==1
    assert 'LEFT BORDER' in g['p1_positive']['inputs']['text']
    assert 'FULL BODY REAR VIEW' in g['p2_positive']['inputs']['text']
    assert 'ENLARGED FRONT-FACING FACE CLOSE-UP' in g['p3_positive']['inputs']['text']
    assert all('RIGHT-FACING FULL BODY' not in n['inputs'].get('text','') for n in g.values())
    assert 'Composition: four panels' not in g['p0_positive']['inputs']['text']
    for i in (1,2):assert g[f'p{i}_portrait_encode']['inputs']['pixels']==['p0_decoded',0]
    assert g['p3_portrait_encode']['inputs']['pixels']==['p0_decoded',0]
    assert g['p0_latent']['inputs']['height']==1152
    assert g['p3_latent']['inputs']['width']>g['p0_latent']['inputs']['width']
    assert g['join3']['inputs']['image2']==['p3_decoded',0]
    assert g['p3_latent']['inputs']['height']==p['height']
    assert not any(n['class_type'] in ('EmptyImage','ImageCompositeMasked') for n in g.values())
    assert g['p3_sigmas']['inputs']['steps']==16
    for n in g.values():
        for v in n['inputs'].values():
            if isinstance(v,list) and len(v)==2 and isinstance(v[1],int):assert v[0] in g


def test_project_projection_preserves_local_retry_and_route(client,plan,monkeypatch):
    pid=create(client,plan);monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    j=engine.enqueue(pid,models.JobRequest(capability='image',target_id='room',image_provider='comfy_local',image_operation='new'))['job']
    projected=next(x for x in client.get('/api/projects/'+pid).json()['jobs'] if x['id']==j['id'])
    assert projected['input']['image_provider']=='comfy_local'
    assert projected['input']['image_operation']=='new'
    assert projected['input']['local_image_plan']==j['input']['local_image_plan']
