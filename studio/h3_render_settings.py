"""User-facing H3 presets and deterministic resolution/step normalization."""
import math
import re
from typing import Literal
from pydantic import Field, model_validator
from . import models, h3_lora_catalog

TURBO8 = 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'
ASPECTS = ['16:9', '9:16', '1:1', '4:3', '3:4', '3:2', '2:3', '21:9']
DEFAULT_MODELS = {'FL2VA': 'minimax_h3_fl2va_pruned_int8_convrot.safetensors',
                  'REF2VA': 'minimax_h3_ref2va_pruned_int8_convrot.safetensors'}


def model_family(name):
    """Recognize H3 base weights; installed availability is checked against UNETLoader."""
    base = str(name).replace('\\', '/').rsplit('/', 1)[-1].lower()
    match = re.fullmatch(r'minimax_h3_(fl2va|ref2va)_[a-z0-9_.-]+\.safetensors', base)
    return match[1].upper() if match else None


def lora_family(name):
    low = name.lower()
    if 'ref2v' in low or 'r2v_' in low:
        return 'REF2VA'
    if 'fl2v' in low:
        return 'FL2VA'
    return None


def recommended_steps(name):
    match = re.search(r'(?:^|_)(4|8)step(?:_|\.)', name.lower())
    return int(match[1]) if match and 'turbo' in name.lower() else 20


def dimensions(aspect, mp):
    a, b = map(int, aspect.split(':'))
    k = math.sqrt(mp * 1024 * 1024 / (a * b))
    return max(256, round(a*k/32)*32), max(256, round(b*k/32)*32)


def defaults(mode='I2VA'):
    lora = '' if mode == 'REF2VA' else TURBO8
    return dict(model=DEFAULT_MODELS['REF2VA' if mode == 'REF2VA' else 'FL2VA'],
                width=864, height=480, aspect_ratio='16:9', megapixels=0.4,
                steps=recommended_steps(lora), cfg=1.0, seed=None,
                acceleration_lora=lora, other_loras=[], audio_mode='generate',
                attention='kitchen', scale=1.0, second_pass=False,
                refine_steps=3, refine_denoise=0.25, upscale_model='',
                sampler='res_multistep', scheduler='simple', shift_video=12.0, shift_audio=3.0)


class Lora(models.Strict):
    name: str = Field(min_length=1, max_length=300)
    strength: float | None = Field(default=None, ge=-2, le=2)


class RenderSettings(models.Strict):
    model: str | None = Field(default=None, min_length=1, max_length=300)
    width: int = Field(default=864, ge=256, le=4096)
    height: int = Field(default=480, ge=256, le=4096)
    # custom preserves the previous width/height API; UI presets send their ratio explicitly.
    aspect_ratio: str = 'custom'
    megapixels: float = Field(default=0.4, ge=0.2, le=2)
    steps: int | None = Field(default=None, ge=1, le=100)
    cfg: float = Field(default=1.0, ge=0, le=10)
    seed: int | None = Field(default=None, ge=0, le=4294967295)
    acceleration_lora: str | None = Field(default=None, max_length=300)
    other_loras: list[Lora] = Field(default_factory=list, max_length=4)
    audio_mode: Literal['generate', 'mute'] = 'generate'
    attention: Literal['kitchen', 'default', 'sage', 'memory_sage'] = 'kitchen'
    scale: Literal[1.0, 1.5, 2.0, 4.0] = 1.0
    second_pass: bool = False
    refine_steps: int = Field(default=3, ge=1, le=100)
    refine_denoise: float = Field(default=0.25, gt=0, le=1)
    upscale_model: str = Field(default='', max_length=300)
    sampler: str = 'res_multistep'
    scheduler: str = 'simple'
    shift_video: float = Field(default=12.0, gt=0, le=100)
    shift_audio: float = Field(default=3.0, gt=0, le=100)

    @model_validator(mode='after')
    def canvas(self):
        if self.aspect_ratio not in [*ASPECTS, 'custom']:
            raise ValueError('不支援的畫面比例。')
        if self.width % 32 or self.height % 32:
            raise ValueError('尺寸須為 32 的倍數。')
        if len({v.name for v in self.other_loras}) != len(self.other_loras):
            raise ValueError('其他 LoRA 不可重複選用。')
        if self.upscale_model and (not self.second_pass or self.scale == 1):
            raise ValueError('放大模型需要同時啟用二採及放大倍數。')
        return self


def normalize(values, mode):
    cfg = RenderSettings.model_validate(values).model_dump()
    for item in cfg['other_loras']:
        if item['strength'] is None:
            item['strength'] = h3_lora_catalog.preset(item['name'])['default_strength']
    family = 'REF2VA' if mode == 'REF2VA' else 'FL2VA'
    if cfg['model'] is None:
        cfg['model'] = DEFAULT_MODELS[family]
    family = model_family(cfg['model'])
    if family is None or (mode != 'REF2VA' and family != 'FL2VA'):
        raise ValueError('所選底模與本鏡 H3 模型家族不符：' + cfg['model'])
    if cfg['acceleration_lora'] is None:
        cfg['acceleration_lora'] = '' if family == 'REF2VA' else TURBO8
    selected = cfg['acceleration_lora']
    for name in [selected, *[x['name'] for x in cfg['other_loras']]]:
        if name and lora_family(name) and lora_family(name) != family:
            raise ValueError('所選 LoRA 與目前底模家族不符：' + name)
    if selected and any(x['name'] == selected for x in cfg['other_loras']):
        raise ValueError('加速 LoRA 不可在其他 LoRA 再掛一次。')
    if any(h3_lora_catalog.is_acceleration(x['name']) for x in cfg['other_loras']):
        raise ValueError('Style LoRA 不接受加速權重，請改用上方的加速 LoRA 選單。')
    if selected and ('turbo' not in selected.lower() or lora_family(selected) is None):
        raise ValueError('加速選單只接受有明確 H3 家族的 Turbo LoRA。')
    # First-pass steps are owned by the accelerator preset, including legacy saved requests.
    cfg['steps'] = recommended_steps(selected)
    if cfg['aspect_ratio'] != 'custom':
        cfg['width'], cfg['height'] = dimensions(cfg['aspect_ratio'], cfg['megapixels'])
    if cfg['width'] * cfg['height'] > 2.2 * 1024 * 1024:
        raise ValueError('一採画面最多 2 MP。')
    return cfg


def output_dimensions(cfg):
    # Refine targets are H3-stride aligned; a standalone pixel resize follows exact scale.
    if cfg.get('second_pass'):
        return tuple(round(cfg[k]*cfg.get('scale',1)/32)*32 for k in ('width','height'))
    return tuple(round(cfg[k]*cfg.get('scale',1)) for k in ('width','height'))
