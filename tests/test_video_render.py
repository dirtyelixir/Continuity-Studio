"""Isolated protocol tests: never submit a live ComfyUI or GPU job."""
import copy
import hashlib
import io
import json
import zipfile
from pathlib import Path

import httpx
import pytest
from studio import store, video_render as vr, comfy_video_provider as provider, h3_render_graph as graph
from test_production import client, plan, create, add_asset
from test_video_workflow import begin, finish, adopt, configure
from test_h3_render_graph import schema


@pytest.fixture
def local(client, plan, monkeypatch, schema):
    monkeypatch.setattr(vr, 'schedule', lambda *args, **kwargs: None)
    pid = create(client, plan)
    add_asset(pid, plan, 'start')
    j = begin(client, pid)
    finish(client, j)
    assert adopt(client, pid, j).status_code == 200
    remote = {'posts': 0, 'uploads': {}, 'graph': None, 'prompt_id': '', 'job_id': '', 'failed': False, 'timeout': False, 'download_fail': False}
    def handler(request):
        path = request.url.path
        if path.startswith('/object_info/'):
            name = path.split('/')[-1]
            return httpx.Response(200, json={name:schema[name]} if name in schema else {})
        if path == '/prompt':
            remote['posts'] += 1
            body = json.loads(request.content)
            remote.update(graph=body['prompt'], prompt_id=body['prompt_id'], job_id=body['extra_data']['continuity_studio_job_id'], extra=body['extra_data'])
            if remote['timeout']:
                raise httpx.ReadTimeout('test-only lost response', request=request)
            return httpx.Response(200, json={'prompt_id': body['prompt_id'], 'node_errors': {}})
        if path.startswith('/history'):
            if not remote['graph']:
                return httpx.Response(200,json={})
            history = {'prompt':[0, remote['prompt_id'],remote['graph'],remote['extra']],
                       'status':{'completed':True,'status_str':'error' if remote['failed'] else 'success','messages':[]},
                       'outputs':{'7':{'images':[{'filename':'video_00001_.mp4','subfolder':'ContinuityStudio/'+remote['job_id'],'type':'output'}]}}}
            return httpx.Response(200,json={remote['prompt_id']:history})
        if path == '/queue':
            return httpx.Response(200,json={'queue_running':[],'queue_pending':[]})
        if path == '/view':
            if remote['download_fail']:
                return httpx.Response(503)
            return httpx.Response(200,content=b'TEST ONLY MOCK VIDEO BYTES, not generated media')
        raise AssertionError('Unexpected protocol request: '+str(request.url))
    from contextlib import nullcontext
    monkeypatch.setattr(vr.comfy_runtime, 'reserve', lambda mode, **kwargs: nullcontext({'mode':mode}))
    monkeypatch.setattr(provider, 'client', lambda: httpx.Client(base_url='http://test-comfy',transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(provider, 'check_guard', lambda c: {'guarded':True,'comfy_pid':123})
    def upload(c, tid, ref, path):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256']
        remote['uploads'][ref['asset_id']] = path.read_bytes()
        return dict(name=ref['asset_id']+'.png',subfolder='ContinuityStudio/'+tid,type='input',verified_sha256=ref['sha256'])
    monkeypatch.setattr(provider, 'upload', upload)
    monkeypatch.setattr(provider, 'probe', lambda path: dict(duration=6.58,width=864,height=480,audio_channels=2))
    return pid, remote


def request_for(client,pid,**settings):
    row=client.get('/api/projects/'+pid).json()['video_renders']['shots']['shot']
    assert row['ready'], row
    return dict(source_hash=row['source_hash'],request_key=store.uid(),settings=settings)


def send(client,pid,request):
    response=client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json=request)
    assert response.status_code==200,response.text
    return response.json()


def test_submit_recover_adopt_export_and_exact_snapshot(client, local):
    pid, remote=local
    before=store.project(pid);assets=store.assets(pid)
    req=request_for(client,pid,seed=42)
    t=send(client,pid,req)
    assert send(client,pid,req)['id']==t['id']
    assert send(client,pid,{**req,'request_key':store.uid()})['id']==t['id']
    assert remote['posts']==0
    vr.run(pid,t['id'])
    done=vr.take(pid,t['id'])
    assert done['state']=='succeeded',done['error']
    assert remote['posts']==1
    assert done['result']['prompt_id']==remote['prompt_id']
    assert done['result']['workflow_hash']==store.digest(remote['graph'])
    assert done['request']['source']['text'] == json.loads(remote['graph']['12']['inputs']['timeline_data'])['segments'][0]['prompt']
    assert client.post(f'/api/projects/{pid}/video-renders/{t["id"]}/adopt',json={'source_hash':req['source_hash']}).status_code==200
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert 'video/'+t['id']+'.mp4' in z.namelist()
        assert json.loads(z.read('video/'+t['id']+'-provenance.json'))['prompt_id']==remote['prompt_id']
    assert store.project(pid)==before and store.assets(pid)==assets


def test_lost_submit_response_recovery_never_posts_twice(client,local):
    pid,remote=local;remote['timeout']=True
    req=request_for(client,pid);t=send(client,pid,req)
    vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='uncertain' and remote['posts']==1
    assert send(client,pid,{**req,'request_key':store.uid()})['id']==t['id']
    remote['timeout']=False
    vr.run(pid,t['id'],resume=True)
    assert vr.take(pid,t['id'])['state']=='succeeded'
    assert remote['posts']==1


def test_download_failure_reuses_original_completed_job(client,local):
    pid,remote=local;remote['download_fail']=True
    t=send(client,pid,request_for(client,pid));vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='recoverable'
    remote['download_fail']=False
    vr.run(pid,t['id'],resume=True)
    assert vr.take(pid,t['id'])['state']=='succeeded' and remote['posts']==1


def test_stale_assets_and_source_prevent_submit_and_adopt(client,local):
    pid,remote=local;req=request_for(client,pid);t=send(client,pid,req)
    with store.db() as c:c.execute("UPDATE assets SET status='rejected' WHERE project_id=?",(pid,))
    vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='failed' and remote['posts']==0
    assert client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json={**req,'request_key':store.uid()}).status_code==400
    assert client.post(f'/api/projects/{pid}/video-renders/{t["id"]}/adopt',json={'source_hash':req['source_hash']}).status_code==400


def test_guards_and_isolation(client,local,plan,monkeypatch):
    pid,remote=local;req=request_for(client,pid)
    other=create(client,plan)
    wrong={**req,'settings':{'width':900}}
    assert client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json=wrong).status_code==422
    t=send(client,pid,req)
    assert client.get(f'/api/projects/{other}/video-renders/{t["id"]}').status_code==400
    assert client.post(f'/api/projects/{other}/video-renders/{t["id"]}/recover',json={}).status_code==400
    def no_guard(c):raise ValueError('VRAM guard unavailable')
    monkeypatch.setattr(provider,'check_guard',no_guard)
    vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='failed' and remote['posts']==0


def test_restart_resumes_queued_but_never_resubmits_preparing_or_submitting(client,local,monkeypatch):
    pid,remote=local;t=send(client,pid,request_for(client,pid));scheduled=[]
    monkeypatch.setattr(vr,'schedule',lambda *args,**kwargs:scheduled.append((args,kwargs)))
    vr.init();assert vr.take(pid,t['id'])['state']=='queued'
    assert scheduled==[((pid,t['id']),{})]
    scheduled.clear()
    vr.update(pid,t['id'],'preparing');vr.init()
    assert vr.take(pid,t['id'])['state']=='failed' and not scheduled
    vr.update(pid,t['id'],'submitting');vr.init()
    assert vr.take(pid,t['id'])['state']=='uncertain'
    assert scheduled==[((pid,t['id']),{'resume':True})] and remote['posts']==0


def test_unrelated_history_and_unsafe_output_rejected():
    fake={'prompt':[0,'pid',{}, {'continuity_studio_job_id':'OTHER','workflow_hash':'hash'}]}
    c=httpx.Client(base_url='http://test',transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'pid':fake})))
    with c,pytest.raises(ValueError,match='不屬於'):
        provider.inspect(c,'job','pid','hash')
    with pytest.raises(ValueError,match='位置'):
        provider.download(None,{'filename':'x.mp4','subfolder':'../secret','type':'output'},'job',Path('/never-written.mp4'))


def test_completed_video_cannot_be_adopted_after_source_edit(client,local):
    pid,remote=local;req=request_for(client,pid);t=send(client,pid,req);vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='succeeded'
    p=client.get('/api/projects/'+pid).json();row=p['video_workflow']['shots'][0]
    changed=row['prompt']['text'].replace('Wind and','A little wind and')
    assert configure(client,pid,text=changed,source_hash=row['source_hash']).status_code==200
    r=client.post(f'/api/projects/{pid}/video-renders/{t["id"]}/adopt',json={'source_hash':req['source_hash']})
    assert r.status_code==400
    assert client.get('/api/projects/'+pid).json()['video_renders']['takes'][0]['current'] is False


def test_failed_history_retained_without_automatic_retry(client,local):
    pid,remote=local;remote['failed']=True;t=send(client,pid,request_for(client,pid));vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='failed' and remote['posts']==1
    assert (vr.folder(t['id'])/'history.json').is_file()


def test_ref2va_source_scope_and_continuation_guard(client,local,plan,monkeypatch):
    from studio import delivery
    pid,remote=local
    add_asset(pid,plan,'ada');add_asset(pid,plan,'room')
    assert configure(client,pid,mode='REF2VA').status_code==200
    # Persist the already compiled complete strings through the real delivery contract.
    p=client.get('/api/projects/'+pid).json();scene=p['delivery']['scenes'][0]
    cfg=delivery.configuration(pid);cfg.update(production_revision=p['revision'])
    cfg['scenes']={'scene':{'global_prompt':scene['global_prompt'],'prompt_edited':True,'chapters':{'shot':{'shot_prompt':scene['chapters'][0]['shot_prompt'],'prompt_edited':True}}}}
    delivery.save_configuration(pid,cfg)
    src=vr.source(store.project(pid),'shot')
    assert src['mode']=='REF2VA' and all(r['scope']=='shared' for r in src['references'])
    assert src['global_prompt']==scene['global_prompt']
    t=send(client,pid,request_for(client,pid));vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='succeeded'
    assert remote['graph']['1']['inputs']['unet_name']==graph.MODELS['REF2VA']
    fake=delivery.project_bundle(store.project(pid));fake['scenes'][0]['chapters'][0]['guidance']['continuityFromPrev']=True
    with pytest.raises(ValueError,match='上一段'):
        vr.source({**store.project(pid),'delivery':fake},'shot')


def test_upload_verifies_actual_received_bytes(tmp_path):
    content=b'test source image';path=tmp_path/'input.png';path.write_bytes(content)
    ref={'asset_id':'asset','sha256':hashlib.sha256(content).hexdigest()}
    tid='0123456789abcdef';calls=[]
    def handler(req):
        calls.append(req.url.path)
        if req.url.path=='/upload/image':return httpx.Response(200,json={'type':'input','subfolder':'ContinuityStudio/'+tid,'name':'asset.png'})
        return httpx.Response(200,content=content)
    with httpx.Client(base_url='http://test',transport=httpx.MockTransport(handler)) as c:
        assert provider.upload(c,tid,ref,path)['name']=='asset.png'
    assert calls==['/upload/image','/view']
    with httpx.Client(base_url='http://test',transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'type':'input','subfolder':'OTHER','name':'asset.png'}))) as c:
        with pytest.raises(ValueError,match='資料夾'):provider.upload(c,tid,ref,path)


@pytest.mark.parametrize('state', vr.UNRESOLVED)
def test_unresolved_video_blocks_project_deletion(client, local, state):
    pid, remote = local
    t = send(client, pid, request_for(client, pid))
    vr.update(pid, t['id'], state)
    p = store.project(pid)
    response = client.request('DELETE', '/api/projects/'+pid,
        json={'confirmation_title':p['title'], 'revision':p['revision']})
    assert response.status_code == 400 and '影片' in response.json()['detail']
    assert store.project(pid)['deleted_at'] is None
    assert remote['posts'] == 0


def test_requested_settings_freeze_step_preset_and_family(client, local):
    pid, remote = local
    req = request_for(client, pid, aspect_ratio='9:16', megapixels=.4, audio_mode='mute', scale=2)
    t = send(client,pid,req)
    cfg = t['request']['settings']
    assert cfg['steps']==8 and cfg['attention']=='kitchen'
    assert (cfg['width'],cfg['height'])==(480,864)
    assert cfg['audio_mode']=='mute' and cfg['scale']==2
    assert not cfg['second_pass'] and not cfg['other_loras']
    assert remote['posts']==0


def test_probe_accepts_video_without_audio_for_caller_policy(monkeypatch):
    import types
    monkeypatch.setattr(provider.subprocess,'run',lambda *a,**k:types.SimpleNamespace(stdout=json.dumps({'streams':[{'codec_type':'video','width':864,'height':480,'avg_frame_rate':'24/1','codec_name':'h264'}],'format':{'duration':'10.125'}})))
    result=provider.probe('not-a-real-file')
    assert result['audio_channels']==0 and result['audio_codec'] is None


def test_live_choice_contract_from_schema(client,local):
    response=client.get('/api/video-provider/options')
    assert response.status_code==200
    options=response.json()
    assert 'kitchen' in options['attention'] and options['frame_rate']==24
    assert options['second_pass_available']
    assert '4x-UltraSharp.pth' in options['upscale_models']
    chosen=next(x for x in options['loras'] if x['name']==graph.render_settings.TURBO8)
    assert chosen['recommended_steps']==8 and chosen['family']=='FL2VA'
    assert all('h3' in x['name'].lower() or 'minimax' in x['name'].lower() for x in options['loras'])


def test_mute_scaled_result_policy_and_recovery(client, local, monkeypatch):
    pid,remote=local
    monkeypatch.setattr(provider,'probe',lambda path:dict(duration=6.58,width=1728,height=960,audio_channels=0))
    t=send(client,pid,request_for(client,pid,audio_mode='mute',scale=2))
    vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='succeeded'
    assert remote['posts']==1
    assert 'audio' not in remote['graph']['6']['inputs']
    assert remote['graph']['30']['inputs']['scale_by']==2


def test_generated_audio_is_required_when_requested(client,local,monkeypatch):
    pid,remote=local
    monkeypatch.setattr(provider,'probe',lambda path:dict(duration=6.58,width=864,height=480,audio_channels=0))
    t=send(client,pid,request_for(client,pid))
    vr.run(pid,t['id'])
    result=vr.take(pid,t['id'])
    assert result['state']=='recoverable' and '缺少音軌' in result['error']


def test_duration_is_locked_to_canonical_shot(client,local):
    pid,remote=local
    p=client.get('/api/projects/'+pid).json()
    canonical=next(s for s in p['production']['shots'] if s['id']=='shot')['duration']
    timing=p['video_renders']['shots']['shot']['timing']
    assert timing==dict(duration=canonical,frame_rate=24,frame_count=graph.frame_count(canonical),aligned_duration=graph.frame_count(canonical)/24)
    req=request_for(client,pid)
    for field in ['duration','frame_rate','frame_count']:
        illegal=copy.deepcopy(req);illegal['settings'][field]=999
        assert client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json=illegal).status_code==422
    illegal=copy.deepcopy(req);illegal['duration']=999
    assert client.post(f'/api/projects/{pid}/video-workflow/shot/generate',json=illegal).status_code==422
    t=send(client,pid,req);vr.run(pid,t['id'])
    timeline=json.loads(remote['graph']['12']['inputs']['timeline_data'])
    assert t['request']['source']['duration']==canonical
    assert remote['graph']['12']['inputs']['total_frames']==graph.frame_count(canonical)
    assert timeline['segments'][0]['durationSec']==canonical


def test_selected_model_frozen_and_used_by_both_passes(client, local):
    pid, remote = local
    name = 'minimax_h3_fl2va_pruned_fp8_scaled.safetensors'
    t = send(client, pid, request_for(client, pid, model=name, second_pass=True))
    assert t['request']['settings']['model'] == name
    vr.run(pid, t['id'])
    assert vr.take(pid, t['id'])['state'] == 'succeeded'
    g = remote['graph']
    assert g['1']['inputs']['unet_name'] == name
    assert g['25']['inputs']['model'] == ['1', 0]
    assert g['22']['inputs']['model'] == ['1', 0]
    assert g['18']['inputs']['refine_model'] == ['22', 0]
    options = client.get('/api/video-provider/options').json()
    assert {'name': name, 'family': 'FL2VA'} in options['models']
    assert all(graph.render_settings.model_family(x['name']) for x in options['models'])


def test_trigger_preview_freeze_and_graph_without_editing_source(client, local, monkeypatch, schema):
    from studio import h3_lora_catalog
    pid, remote = local
    names=['camera_motion_h3_lora_v1_3000_pruned.safetensors','h3-realism-people-t2v-i2v-r2v.safetensors']
    available=schema['LoraLoaderModelOnly']['input']['required']['lora_name'][0]
    available.extend(n for n in names if n not in available)
    settings={'other_loras':[{'name':n,'strength':.9} for n in names]}
    req=request_for(client,pid,**settings)
    before=vr.source(store.project(pid),'shot')
    preview=client.post(f'/api/projects/{pid}/video-workflow/shot/prompt-preview',json=settings)
    assert preview.status_code==200,preview.text
    assert not vr.state(store.project(pid))['takes'] and remote['posts']==0
    t=send(client,pid,req)
    assert t['request']['source']==before
    assert t['request']['prompt_assembly']==preview.json()
    assert t['request']['prompt_assembly']['text']=='camera motion; r34l1sm\n\n'+before['text']
    # The submitted take must use its frozen activation metadata, even if the catalog changes.
    monkeypatch.setattr(h3_lora_catalog,'preset',lambda name:{'trigger':'CHANGED','default_strength':1})
    vr.run(pid,t['id'])
    assert vr.take(pid,t['id'])['state']=='succeeded'
    timeline=json.loads(remote['graph']['12']['inputs']['timeline_data'])
    assert timeline['segments'][0]['prompt']==preview.json()['text']
    assert vr.source(store.project(pid),'shot')==before
    assert remote['posts']==1
