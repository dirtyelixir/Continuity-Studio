"""Explicit, source-backed display and strength presets; never infer strength from rank."""
from pathlib import PurePosixPath

PRESETS = {
    'camera_motion_h3_lora_v1_3000_pruned.safetensors': {
        'description': '加強提示詞對鏡頭運動的控制，例如推近、拉遠、手持跟拍與環繞，適合需要明確運鏡的鏡頭。',
        'label': '運鏡 · Camera Motion', 'default_strength': 1.0,
        'recommended_strength': [0.8, 1.0], 'strength_basis': 'author_range',
        'trigger': 'camera motion',
        'source_url': 'https://huggingface.co/Jojocodex/minimax-h3-Camera-Motion-lora',
    },
    'h3-realism-people-t2v-i2v-r2v.safetensors': {
        'description': '加強人物皮膚質感、臉部細節、自然表情與動作，適合人物近鏡和寫實生活場景。',
        'label': '人物寫實 · Realism People', 'default_strength': 1.0,
        'recommended_strength': [1.0, 1.0], 'strength_basis': 'author_default',
        'trigger': 'r34l1sm',
        'source_url': 'https://huggingface.co/fal/MiniMax-H3-Realism-People-LoRA',
    },
}


def is_acceleration(name):
    return 'turbo' in PurePosixPath(name).name.lower()


def description(name):
    base = PurePosixPath(name).name
    if base in PRESETS:
        return PRESETS[base]['description']
    if 'turbo' in base and 'fl2v' in base:
        steps = 8 if '8step' in base else 4
        return f'以 {steps} 步採樣加快首幀／首尾幀影片生成，適合快速試拍；使用 FL2VA 底模。'
    if 'turbo' in base and 'ref2v' in base:
        return '以 4 步採樣加快參考圖生影片，適合快速試拍角色、場景與道具組合；使用 Ref2VA 底模。'
    if base == 'minimax_h3_turbo_4step_ckpt600_ema_V4.safetensors':
        return 'H3 Turbo V4 加速權重，供較少步數的影片採樣使用；實際步數與底模須配合作者工作流。'
    return '尚未有已核對的用途說明；請參閱此 LoRA 的作者文件。'


def preset(name):
    return {'purpose': 'acceleration' if is_acceleration(name) else 'style', 'description': description(name), ** PRESETS.get(PurePosixPath(name).name, {
        'label': name, 'default_strength': 1.0, 'recommended_strength': None,
        'strength_basis': 'unverified', 'trigger': '', 'source_url': '',
    }).copy()}
