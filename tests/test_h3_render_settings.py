import pytest
from studio import h3_render_settings as s


def test_requested_defaults_and_override():
    cfg=s.normalize({},'I2VA')
    assert cfg['acceleration_lora']==s.TURBO8 and cfg['steps']==8
    assert (cfg['width'],cfg['height'])==(864,480)
    assert cfg['attention']=='kitchen' and cfg['audio_mode']=='generate'
    assert not cfg['second_pass'] and cfg['scale']==1 and not cfg['other_loras']
    assert s.normalize({'steps':12},'FL2VA')['steps']==8
    assert s.normalize({'acceleration_lora':''},'FL2VA')['steps']==20
    turbo4='minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors'
    assert s.normalize({'acceleration_lora':turbo4},'FL2VA')['steps']==4
    assert s.normalize({'acceleration_lora':turbo4,'steps':6},'FL2VA')['steps']==4


def test_family_mismatch_never_silent():
    assert s.normalize({},'REF2VA')['acceleration_lora']==''
    assert s.normalize({},'REF2VA')['steps']==20
    with pytest.raises(ValueError,match='家族'):
        s.normalize({'acceleration_lora':s.TURBO8},'REF2VA')
    with pytest.raises(ValueError,match='家族'):
        s.normalize({'other_loras':[{'name':'minimax_h3_ref2v_turbo_8step.safetensors'}]},'I2VA')
    with pytest.raises(ValueError,match='再掛'):
        s.normalize({'other_loras':[{'name':s.TURBO8}]},'I2VA')


@pytest.mark.parametrize('ratio,mp,expected',[('16:9',.4,(864,480)),('9:16',.4,(480,864)),('1:1',.4,(640,640)),('16:9',1,(1376,768))])
def test_director_resolution_math(ratio,mp,expected):
    cfg=s.normalize({'aspect_ratio':ratio,'megapixels':mp},'I2VA')
    assert (cfg['width'],cfg['height'])==expected
    cfg['scale']=1.5
    assert s.output_dimensions(cfg)==tuple(round(n*1.5) for n in expected)
    cfg['second_pass']=True
    assert s.output_dimensions(cfg)==tuple(round(n*1.5/32)*32 for n in expected)


@pytest.mark.parametrize('bad',[
    {'scale':3},{'megapixels':4},{'audio_mode':'source'},{'attention':'invented'},
    {'width':850},{'aspect_ratio':'weird'},{'steps':0},
    {'second_pass':False,'scale':2,'upscale_model':'4x-UltraSharp.pth'},
    {'other_loras':[{'name':'a'},{'name':'a'}]},
])
def test_invalid_settings(bad):
    with pytest.raises(ValueError):s.normalize(bad,'I2VA')


def test_lora_strength_default_has_source_and_override_survives():
    from studio import h3_lora_catalog
    name='camera_motion_h3_lora_v1_3000_pruned.safetensors'
    preset=h3_lora_catalog.preset(name)
    assert preset['recommended_strength']==[.8,1.0]
    assert preset['default_strength']==1.0 and preset['trigger']=='camera motion'
    assert preset['source_url'].startswith('https://huggingface.co/Jojocodex/')
    cfg=s.normalize({'other_loras':[{'name':name}]},'I2VA')
    assert cfg['other_loras'][0]['strength']==1.0
    assert s.normalize({'other_loras':[{'name':name,'strength':.85}]},'I2VA')['other_loras'][0]['strength']==.85
    assert h3_lora_catalog.preset('unknown_h3.safetensors')['recommended_strength'] is None


@pytest.mark.parametrize('name',[
 'minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors',
 'minimax_h3_turbo_4step_ckpt600_ema_V4.safetensors',
])
def test_acceleration_cannot_be_used_as_style(name):
    from studio import h3_lora_catalog
    assert h3_lora_catalog.preset(name)['purpose']=='acceleration'
    with pytest.raises(ValueError,match='Style LoRA'):
        s.normalize({'other_loras':[{'name':name}]},'I2VA')
    assert h3_lora_catalog.preset('camera_motion_h3_lora_v1_3000_pruned.safetensors')['purpose']=='style'


@pytest.mark.parametrize('mode', ['I2VA', 'FL2VA', 'REF2VA'])
def test_base_model_defaults_and_family(mode):
    family = 'REF2VA' if mode == 'REF2VA' else 'FL2VA'
    assert s.normalize({}, mode)['model'] == s.defaults(mode)['model'] == s.DEFAULT_MODELS[family]
    for invalid in ['flux.safetensors'] + ([s.DEFAULT_MODELS['REF2VA']] if mode != 'REF2VA' else []):
        with pytest.raises(ValueError, match='家族'):
            s.normalize({'model': invalid}, mode)


def test_ref2v_can_use_fl2va_base_and_its_accelerator():
    cfg = s.normalize({'model': s.DEFAULT_MODELS['FL2VA']}, 'REF2VA')
    assert cfg['acceleration_lora'] == s.TURBO8 and cfg['steps'] == 8
    cfg = s.normalize({'model': s.DEFAULT_MODELS['FL2VA'], 'acceleration_lora': '', 'steps': 12}, 'REF2VA')
    assert cfg['steps'] == 20 and cfg['acceleration_lora'] == ''
    with pytest.raises(ValueError, match='底模家族'):
        s.normalize({'model': s.DEFAULT_MODELS['FL2VA'], 'acceleration_lora': 'minimax_h3_ref2v_turbo_4step.safetensors'}, 'REF2VA')
