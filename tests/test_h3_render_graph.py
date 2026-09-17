import copy
import json
from pathlib import Path

import pytest
from studio import h3_render_graph as graph

JOB = '0123456789abcdef'


@pytest.fixture
def schema():
    return json.loads((Path(__file__).parent / 'fixtures/h3_node_schema.json').read_text())


def compile_graph(schema, mode='I2VA'):
    refs = [{'asset_id': 'a', 'label': 'Picture 1', 'moment': 'start', 'scope': 'shared'}]
    if mode != 'I2VA':
        refs.append({'asset_id': 'b', 'label': 'Picture 2', 'moment': 'end', 'scope': 'local'})
    source = dict(mode=mode, shot_id='real-shot', duration=10, text='EXACT saved Shot prompt\n<d>[粵語] 行啦。</d>',
                  global_prompt='EXACT Scene global', references=refs)
    uploaded = {r['asset_id']: dict(name=r['asset_id'] + '.png', subfolder='ContinuityStudio/' + JOB, type='input') for r in refs}
    result = graph.build_graph(source, uploaded, {**graph.defaults(mode), 'seed': 123}, JOB, schema)
    return source, result, json.loads(result['12']['inputs']['timeline_data'])


@pytest.mark.parametrize('mode', ['I2VA', 'FL2VA', 'REF2VA'])
def test_mode_and_exact_media_prompt_contract(schema, mode):
    source, g, timeline = compile_graph(schema, mode)
    assert {'1','2','3','4','6','7','8','12','17'} <= set(g)
    assert ('25' in g) == (mode != 'REF2VA')
    assert g['1']['inputs']['unet_name'] == graph.MODELS['REF2VA' if mode == 'REF2VA' else 'FL2VA']
    assert g['12']['inputs']['steps'] == (20 if mode == 'REF2VA' else 8) and g['12']['inputs']['seed'] == 123
    assert timeline['segments'][0]['prompt'] == source['text']
    assert timeline['segments'][0]['durationSec'] == 10
    assert timeline['totalFrames'] == 243
    assert timeline['output']['continuityEnabled'] is False
    assert timeline['segments'][0]['continuityFromPrev'] is False
    if mode == 'REF2VA':
        assert timeline['global']['prompt'] == source['global_prompt']
        assert timeline['global']['refs'][0]['index'] == 0
        assert timeline['segments'][0]['refs'][0]['index'] == 1
    else:
        shot = timeline['shots'][0]
        assert shot['startImage']['imageFile'].endswith('/a.png')
        assert bool(shot['endImage']) == (mode == 'FL2VA')
        assert not timeline['global']['prompt'] and not timeline['global']['refs']
    assert g['7']['inputs']['format'] == 'mp4'
    assert g['7']['inputs']['format.codec'] == 'h264'
    assert g['7']['inputs']['filename_prefix'] == 'ContinuityStudio/' + JOB + '/video'
    assert g['6']['inputs']['audio'] == ['12', 1]
    assert '9246042' not in json.dumps(g)
    assert g['17']['class_type'] == 'ModelAttentionBackend'
    assert g['17']['inputs']['attention'] == 'comfy kitchen attention'


def test_missing_model_or_node_and_wrong_connection(schema):
    missing = copy.deepcopy(schema)
    missing['UNETLoader']['input']['required']['unet_name'][0] = []
    with pytest.raises(ValueError, match='模型'):
        compile_graph(missing)
    del schema['SaveVideo']
    with pytest.raises(ValueError, match='缺少節點'):
        compile_graph(schema)


def test_no_path_escape_no_silent_continuation(schema):
    for item in [dict(name='../a.png', subfolder='', type='input'), dict(name='a.png', subfolder='../bad', type='input'), dict(name='a.png', subfolder='', type='output')]:
        with pytest.raises(ValueError):
            graph.media_path(item)
    source, _, _ = compile_graph(schema)
    source['guide_from_previous'] = True
    with pytest.raises(ValueError, match='上段'):
        graph.build_graph(source, {}, graph.defaults(), JOB, schema)


def test_default_turbo_chain_and_no_optional_sampling(schema):
    _, g, _ = compile_graph(schema)
    assert g['25']['inputs']==dict(model=['1',0],lora_name=graph.render_settings.TURBO8,strength_model=1.0)
    assert g['17']['inputs']['model']==['25',0]
    assert g['12']['inputs']['model']==['17',0]
    assert 'refine' not in g['12']['inputs'] and '30' not in g


@pytest.mark.parametrize('mode',['I2VA','FL2VA','REF2VA'])
@pytest.mark.parametrize('scale',[1,1.5,2])
def test_refine_real_graph_connections(schema,mode,scale):
    src, old, _=compile_graph(schema,mode)
    uploaded={r['asset_id']:dict(name=r['asset_id']+'.png',subfolder='test',type='input') for r in src['references']}
    extra='camera_motion_h3_lora_v1_3000_pruned.safetensors'
    cfg={**graph.defaults(mode),'second_pass':True,'scale':scale,'other_loras':[{'name':extra,'strength':.6}],'seed':123}
    if scale!=1:cfg['upscale_model']='4x-UltraSharp.pth'
    g=graph.build_graph(src,uploaded,cfg,JOB,schema)
    assert g['12']['inputs']['refine']==['18',0]
    assert g['18']['inputs']['mode']==('refine' if scale==1 else 'upscale')
    assert g['18']['inputs']['skip_fl2v'] is False
    assert g['18']['inputs']['confirm_first_pass'] is False
    assert g['20']['inputs']['model']==g['18']['inputs']['refine_model']==['22',0]
    assert g['22']['inputs']['model']==['40',0]  # creative LoRA, without one-pass Turbo
    assert g['20']['inputs']['steps']==3 and g['20']['inputs']['denoise']==.25
    assert g['40']['inputs']['strength_model']==.6
    assert (g['18']['inputs']['width'],g['18']['inputs']['height'])==graph.render_settings.output_dimensions(cfg)
    if scale!=1:assert g['19']['inputs']['model_name']=='4x-UltraSharp.pth'


def test_pixel_scale_mute_and_preset_steps(schema):
    src,_,_=compile_graph(schema)
    cfg={**graph.defaults(),'scale':1.5,'audio_mode':'mute','steps':11,'attention':'default','seed':12}
    g=graph.build_graph(src,{'a':dict(name='a.png',subfolder='test',type='input')},cfg,JOB,schema)
    assert g['6']['inputs']['images']==['30',0] and 'audio' not in g['6']['inputs']
    assert g['30']['inputs']['scale_by']==1.5
    assert json.loads(g['12']['inputs']['timeline_data'])['output']['audioMode']=='mute'
    assert g['12']['inputs']['steps']==8 and '17' not in g
    assert '18' not in g and '20' not in g


@pytest.mark.parametrize('missing',['turbo','kitchen','refine'])
def test_selected_features_fail_when_unavailable(schema,missing):
    src,_,_=compile_graph(schema)
    cfg={**graph.defaults(),'seed':1}
    if missing=='turbo':schema['LoraLoaderModelOnly']['input']['required']['lora_name'][0]=[]
    elif missing=='kitchen':schema['ModelAttentionBackend']['input']['required']['attention'][0]=['pytorch attention']
    else:del schema['MiniMaxH3DirectorRefine'];cfg['second_pass']=True
    with pytest.raises(ValueError):graph.build_graph(src,{'a':dict(name='a.png',subfolder='test',type='input')},cfg,JOB,schema)


def test_uninstalled_model_rejected_without_fallback(schema):
    src, _, _ = compile_graph(schema)
    cfg = {**graph.defaults(), 'seed': 1, 'model': 'minimax_h3_fl2va_missing.safetensors'}
    with pytest.raises(ValueError, match='模型'):
        graph.build_graph(src, {'a': dict(name='a.png', subfolder='test', type='input')}, cfg, JOB, schema)


def test_ref2v_fl2va_base_preserves_reference_conditioning(schema):
    src, _, original = compile_graph(schema, 'REF2VA')
    cfg = {**graph.defaults('REF2VA'), 'model': graph.MODELS['FL2VA'],
           'acceleration_lora': graph.render_settings.TURBO8, 'steps': 8, 'seed': 1, 'second_pass': True}
    uploaded = {r['asset_id']: dict(name=r['asset_id']+'.png', subfolder='test', type='input') for r in src['references']}
    g = graph.build_graph(src, uploaded, cfg, JOB, schema)
    assert g['1']['inputs']['unet_name'] == graph.MODELS['FL2VA']
    assert g['12']['inputs']['task_type'].startswith('r2v')
    timeline = json.loads(g['12']['inputs']['timeline_data'])
    assert timeline['global']['prompt'] == original['global']['prompt']
    assert len(timeline['global']['refs']) == len(original['global']['refs']) == 1
    assert len(timeline['segments'][0]['refs']) == 1
    assert g['25']['inputs']['model'] == g['22']['inputs']['model'] == ['1', 0]
