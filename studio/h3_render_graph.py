"""Deterministic API graph derived from the archived Director's active main chain."""
import copy
import math
import re
from pathlib import PurePosixPath

from . import store, h3_render_settings as render_settings

ORIGINAL = store.ROOT / 'workflows/minimax-h3-director/original/MiniMax+H3+导演台全能工作流 (1).json'
ORIGINAL_SHA256 = 'fa40539a002264b292e6bcb990bc8d2f3788f90f4cadcaf6c67f2a726aa925be'
CLASSES = ('UNETLoader', 'CLIPLoader', 'VAELoader', 'MiniMaxH3Director', 'CreateVideo', 'SaveVideo', 'PreviewAny')
MODELS = render_settings.DEFAULT_MODELS


def defaults(mode='I2VA'):
    return render_settings.defaults(mode)


def frame_count(duration):
    n = math.ceil(duration * 24)
    return n + (5 - n % 17) % 17


def media_path(item):
    name, folder = item.get('name', ''), item.get('subfolder', '')
    if item.get('type') != 'input' or not name or '/' in name or '\\' in name:
        raise ValueError('ComfyUI 素材回條無效。')
    path = PurePosixPath(folder) / name
    if path.is_absolute() or '..' in path.parts or '\\' in folder:
        raise ValueError('ComfyUI 素材位置無效。')
    return str(path)


def _inputs(schema):
    return {**schema.get('input', {}).get('required', {}), **schema.get('input', {}).get('optional', {})}


def _selected_task(info, key):
    options = _inputs(info['MiniMaxH3Director'])['task_type'][0]
    return next((v for v in options if v == key or v.startswith(key + ' ')), None)


def _check_value(value, spec, label):
    kind, meta = spec[0], spec[1] if len(spec) > 1 else {}
    if kind == 'COMBO':
        kind = meta.get('options', [])
    if isinstance(value, list):  # Graph connection; checked against source node below.
        return
    if isinstance(kind, list) and value not in kind:
        raise ValueError(f'ComfyUI 未提供所選設定／模型：{label} = {value}')
    if kind in ('INT', 'FLOAT'):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'無效數值：{label}')
        if kind == 'INT' and not isinstance(value, int):
            raise ValueError(f'需要整數：{label}')
        if value < meta.get('min', -math.inf) or value > meta.get('max', math.inf):
            raise ValueError(f'數值超出節點範圍：{label}')


def _dynamic(inputs, name, spec):
    """Comfy v3 DynamicCombo serializes nested controls with dotted input names."""
    options = spec[1]['options']
    desired = {'format': 'mp4', 'format.codec': 'h264'}.get(name)
    option = next((v for v in options if v['key'] == desired), None)
    if desired and option is None:
        raise ValueError('ComfyUI 未提供 MP4／H.264 輸出。')
    option = option or next((v for v in options if v['key'] == 'auto'), options[0])
    inputs[name] = option['key']
    for child, child_spec in option.get('inputs', {}).get('required', {}).items():
        key = name + '.' + child
        if child_spec[0] == 'COMFY_DYNAMICCOMBO_V3':
            _dynamic(inputs, key, child_spec)
        else:
            inputs[key] = child_spec[1].get('default') if len(child_spec) > 1 else None
            if inputs[key] is None:
                raise ValueError('ComfyUI 輸出格式有未支援的必要設定：' + key)


def validate_graph(graph, info):
    for node in graph.values():
        if node['class_type'] not in info:
            raise ValueError('ComfyUI 缺少節點：' + node['class_type'])
    for node in graph.values():
        cls, values = node['class_type'], node['inputs']
        if cls not in info:
            raise ValueError('ComfyUI 缺少節點：' + cls)
        schema = _inputs(info[cls])
        for name, spec in info[cls]['input'].get('required', {}).items():
            if name not in values:
                meta = spec[1] if len(spec) > 1 else {}
                if spec[0] == 'BDGROUP' and 'default' in meta:
                    values[name] = meta['default']
                else:
                    raise ValueError(f'ComfyUI 節點格式不相容：{cls}.{name}')
        for name, value in values.items():
            if name not in schema:
                if '.' in name and schema.get(name.split('.')[0], [None])[0] == 'COMFY_DYNAMICCOMBO_V3':
                    continue
                raise ValueError(f'ComfyUI 未支援輸入：{cls}.{name}')
            _check_value(value, schema[name], cls + '.' + name)
            if isinstance(value, list):
                if len(value) != 2 or value[0] not in graph or not isinstance(value[1], int):
                    raise ValueError('影片工作流連線無效。')
                output = info[graph[value[0]]['class_type']].get('output', [])
                expected = schema[name][0]
                if not 0 <= value[1] < len(output) or (expected != '*' and output[value[1]] != expected):
                    raise ValueError(f'影片工作流連線型別不符：{cls}.{name}')
    return graph


def build_graph(source, uploaded, settings, job_id, object_info):
    from . import storyboard_usage,conditioning
    storyboard_usage.check_graph_source(source)
    conditioning.check_source(source)
    info = object_info
    for cls in CLASSES:
        if cls not in info:
            raise ValueError('ComfyUI 缺少節點：' + cls)
    mode = source['mode']
    if mode not in ('I2VA', 'FL2VA', 'REF2VA') or not re.fullmatch(r'[a-f0-9]{16}', job_id):
        raise ValueError('影片模式或工作編號無效。')
    if source.get('guide_from_previous'):
        raise ValueError('此鏡需要上段影片引導，不能當作獨立鏡頭送出。')
    cfg = render_settings.normalize(settings, mode)
    task = _selected_task(info, 'r2v' if mode == 'REF2VA' else 'fl2v')
    if not task:
        raise ValueError('ComfyUI 導演台未提供所需模式。')
    count = frame_count(source['duration'])
    refs = source['references']
    if not refs or len(refs) > 9:
        raise ValueError('影片需要 1–9 張有效參考圖片。')
    pictures = {}
    for ref in refs:
        label = re.fullmatch(r'Picture ([1-9])', ref['label'])
        if not label or int(label[1]) in pictures or ref['asset_id'] not in uploaded:
            raise ValueError('影片圖片編號或上傳結果不完整。')
        pictures[int(label[1])] = {'index': int(label[1]) - 1, 'imageFile': media_path(uploaded[ref['asset_id']])}
    segment = dict(id=source['shot_id'], start=0, length=count, frameCount=count,
                   durationSec=source['duration'], prompt=source['text'], taskType=task,
                   continuityFromPrev=False, refs=[], refAudios=[], refVideos=[])
    global_block = dict(taskType=task, commonEnabled=mode == 'REF2VA',
                        prompt=source['global_prompt'] if mode == 'REF2VA' else '',
                        refs=[], refAudios=[], refVideos=[], continuousReference=False)
    if mode == 'REF2VA':
        for ref in refs:
            n = int(ref['label'].split()[-1])
            (global_block if ref.get('scope') == 'shared' else segment)['refs'].append(pictures[n])
    else:
        expected = [1, 2] if mode == 'FL2VA' else [1]
        if sorted(pictures) != expected:
            raise ValueError('首／尾幀數量與影片模式不符。')
        segment['startImage'] = pictures[1]
        segment['endImage'] = pictures.get(2)
    timeline = dict(version=5, timelineMode='prompt_batch' if mode == 'REF2VA' else 'fl2v',
                    editMode='segment', frameRate=24, totalFrames=count, segments=[segment],
                    shots=[copy.deepcopy(segment)], **{'global': global_block},
                    output=dict(mode='fixed', width=cfg['width'], height=cfg['height'], frameRate=24,
                                exportMode='all', audioMode=cfg['audio_mode'], continuityEnabled=False,
                                continuityOverlapFrames=22, refImageSize='match'))
    def node(cls, **inputs):
        return dict(class_type=cls, inputs=inputs)
    graph = {
        '1': node('UNETLoader', unet_name=cfg['model'], weight_dtype='default'),
        '2': node('CLIPLoader', clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors', type='minimax', device='default'),
        '3': node('VAELoader', vae_name='minimax_h3_video_vae_fp16.safetensors'),
        '4': node('VAELoader', vae_name='minimax_h3_audio_vae_fp32.safetensors'),
        '12': node('MiniMaxH3Director', model=['1', 0], clip=['2', 0], video_vae=['3', 0], audio_vae=['4', 0],
                   task_type=task, global_prompt=global_block['prompt'], frame_rate=24,
                   width=cfg['width'], height=cfg['height'], ref_max_size=max(cfg['width'], cfg['height']),
                   total_frames=count, timeline_data=store.encode(timeline),
                   **{k: cfg[k] for k in ('steps', 'cfg', 'seed', 'sampler', 'scheduler', 'shift_video', 'shift_audio')}),
        '6': node('CreateVideo', images=['12', 0], audio=['12', 1], fps=['12', 2]),
        '7': node('SaveVideo', video=['6', 0], filename_prefix=f'ContinuityStudio/{job_id}/video'),
        '8': node('PreviewAny', source=['12', 5]),
    }
    configure_graph(graph, info, cfg)
    save = _inputs(info['SaveVideo'])
    if save.get('format', [None])[0] == 'COMFY_DYNAMICCOMBO_V3':
        _dynamic(graph['7']['inputs'], 'format', save['format'])
    else:
        graph['7']['inputs'].update(format='mp4', codec='h264')
    # Explicitly turn off the optional source-image output; retain installed memory policy.
    director_schema = _inputs(info['MiniMaxH3Director'])
    if 'export_source_images' in director_schema:
        graph['12']['inputs']['export_source_images'] = False
    return validate_graph(graph, info)


def configure_graph(g, info, cfg):
    """Wire selected features; inactive options never insert executable nodes."""
    def add(key, cls, **inputs):
        g[key] = dict(class_type=cls, inputs=inputs)
        return [key, 0]
    base = ['1', 0]
    other = base
    for i, item in enumerate(cfg['other_loras']):
        other = add(str(40+i), 'LoraLoaderModelOnly', model=other, lora_name=item['name'], strength_model=item['strength'])
    first = other
    if cfg['acceleration_lora']:
        first = add('25', 'LoraLoaderModelOnly', model=first, lora_name=cfg['acceleration_lora'], strength_model=1.0)
    first = apply_attention(g, first, cfg['attention'], '17', info)
    g['12']['inputs']['model'] = first
    if cfg['second_pass']:
        # Second pass uses the base + chosen creative LoRAs, without the first-pass Turbo.
        second = apply_attention(g, other, cfg['attention'], '22', info)
        sigmas = add('20', 'BasicScheduler', model=second, scheduler='beta', steps=cfg['refine_steps'], denoise=cfg['refine_denoise'])
        w, h = render_settings.output_dimensions(cfg)
        spec = _inputs(info.get('MiniMaxH3DirectorRefine', {}))
        latent = spec.get('latent_upscale_model', [['']])[0]
        if not isinstance(latent, list) or not latent:
            raise ValueError('二採節點缺少必要 latent 模型選項；未送出影片。')
        refine = add('18', 'MiniMaxH3DirectorRefine', refine_model=second, sigmas=sigmas,
                     mode='upscale' if cfg['scale'] != 1 else 'refine', upscale_method='lanczos',
                     latent_upscale_model=latent[0], sampler='euler', passes=1,
                     seed_mode='inherit', aspect_ratio='自定义', megapixels=cfg['megapixels'],
                     width=w, height=h, skip_fl2v=False, confirm_first_pass=False)
        if cfg['upscale_model']:
            g['18']['inputs']['upscale_model'] = add('19', 'UpscaleModelLoader', model_name=cfg['upscale_model'])
        g['12']['inputs']['refine'] = refine
    elif cfg['scale'] != 1:
        g['6']['inputs']['images'] = add('30', 'ImageScaleBy', image=['12', 0], upscale_method='lanczos', scale_by=cfg['scale'])
    if cfg['audio_mode'] == 'mute':
        g['6']['inputs'].pop('audio')


ATTENTION_CLASSES = {'kitchen': 'ModelAttentionBackend',
                     'sage': 'PathchSageAttentionKJ',
                     'memory_sage': 'MiniMaxH3MemoryEfficientSageAttentionPatch'}
OPTIONAL_CLASSES = ('LoraLoaderModelOnly', *ATTENTION_CLASSES.values(), 'MiniMaxH3DirectorRefine',
                    'BasicScheduler', 'UpscaleModelLoader', 'ImageScaleBy')


def apply_attention(g, model, choice, key, info):
    if choice == 'default':
        return model
    cls = ATTENTION_CLASSES[choice]
    if cls not in info:
        raise ValueError('ComfyUI 缺少所選 Attention 節點：' + cls)
    inputs = {'model': model}
    if choice == 'kitchen':
        inputs['attention'] = 'comfy kitchen attention'
    if choice == 'sage':
        inputs.update(sage_attention='auto', allow_compile=False)
    g[key] = dict(class_type=cls, inputs=inputs)
    return [key, 0]
