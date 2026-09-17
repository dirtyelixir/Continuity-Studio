"""Explicit workspace-wide creative providers; image rendering is chosen separately."""
import os
import re
import json
import tempfile
import httpx
from . import store

DEFAULT_CONFIG = {'model': 'deepseek-flash', 'vision_model': 'deepseek-flash', 'key_env': 'DEEPSEEK_API_KEY'}
TEXT_MODELS = ('deepseek-flash', 'deepseek-v4-pro', 'deepseek-v4-flash')
VISION_MODELS = ('deepseek-flash', 'deepseek-v4-flash-vision-exp', 'deepseek-v4-flash')
LEGACY_MODEL_ALIASES = {
    'deepseek-v4-flash': 'deepseek-flash',
    'deepseek-v4-flash-vision-exp': 'deepseek-flash',
}
CREDENTIAL_FILE = 'studio-credentials.json'


def config():
    return {**DEFAULT_CONFIG, **store.setting('deepseek_config', {})}


def credential_value(name):
    """Read a provider credential without exposing it through settings."""
    value = os.environ.get(name, '') if name else ''
    if value:
        return value
    path = store.DATA / CREDENTIAL_FILE
    try:
        with path.open() as fh:
            value = json.load(fh).get(name, '')
            return value if isinstance(value, str) else ''
    except (OSError, ValueError, TypeError, AttributeError):
        return ''


def save_credential(name, value):
    """Store a locally entered credential with owner-only permissions."""
    store.DATA.mkdir(parents=True, exist_ok=True)
    path = store.DATA / CREDENTIAL_FILE
    try:
        with path.open() as fh:
            credentials = json.load(fh)
    except (OSError, ValueError, TypeError):
        credentials = {}
    credentials[name] = value
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=store.DATA, prefix='.studio-credentials-', delete=False) as fh:
            temp_path = fh.name
            fh.write(store.encode(credentials))
            fh.flush()
            os.fchmod(fh.fileno(), 0o600)
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def settings(capabilities=None):
    from . import providers
    default = store.setting('default_provider', 'astra')
    routes = providers.routing()
    caps = set(providers.BUILTINS + list(capabilities or []) + list(routes)) - {'*'}
    image = routes.get('image', default)
    mode = 'custom'
    if default == 'astra' and all(routes.get(c, default) == 'astra' for c in caps if c != 'image'):
        mode = 'astra'
    elif default == 'local_qwen' and all(routes.get(c, default) == default for c in caps if c != 'image'):
        renderer = next((p for p in providers.all_providers() if p['id'] == image), None)
        if renderer and providers.supports(renderer, 'image'):
            mode = 'local_qwen'
    elif default == 'deepseek' and all(routes.get(c, default) == 'deepseek' for c in caps if c != 'image'):
        renderer = next((p for p in providers.all_providers() if p['id'] == image), {})
        if renderer.get('kind') in ('http', 'manual', 'comfy'):
            mode = 'deepseek'
    cfg = config()
    return {'mode': mode, 'default_provider': default, 'deepseek': {**cfg, 'credential_configured': bool(credential_value(cfg['key_env']))}, 'image_provider': image}


def apply(mode, image_provider=None, model=DEFAULT_CONFIG['model'], vision_model=DEFAULT_CONFIG['vision_model'], key_env=DEFAULT_CONFIG['key_env'], api_key=None, capabilities=None):
    from . import providers
    if mode not in ('astra', 'deepseek', 'local_qwen'):
        raise ValueError('請選擇 Astra、DeepSeek 或 Qwen3.8。')
    cfg = config() if mode == 'local_qwen' else {'model': model.strip(), 'vision_model': vision_model.strip(), 'key_env': key_env.strip()}
    if cfg['model'] not in TEXT_MODELS or cfg['vision_model'] not in VISION_MODELS:
        raise ValueError('請選擇支援的 DeepSeek 文字與視覺模型。')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,99}', cfg['key_env']):
        raise ValueError('請輸入憑證環境變數名稱，不能輸入 API Key 本身。')
    image_provider = image_provider or ('astra' if mode == 'astra' else 'manual')
    renderer = next((p for p in providers.all_providers() if p['id'] == image_provider), None)
    if not renderer or not providers.supports(renderer, 'image'): raise ValueError('請選擇有效的圖片生成服務。')
    if mode == 'deepseek':
        renderer = next((p for p in providers.all_providers() if p['id'] == image_provider), None)
        if not renderer or renderer['kind'] not in ('manual', 'http', 'comfy') or not ('image' in renderer['capabilities'] or '*' in renderer['capabilities']):
            raise ValueError('DeepSeek 不提供圖片生成；請明確選擇本機 ComfyUI、外部圖片 API 或人工匯入，不能使用 Astra。')
    if mode != 'local_qwen' and api_key and api_key.strip():
        save_credential(cfg['key_env'], api_key.strip())
    with store.db() as conn:
        row = conn.execute('SELECT value FROM settings WHERE key=?', ('routing',)).fetchone()
        routes = json.loads(row['value']) if row else {}
        caps = set(providers.BUILTINS + list(capabilities or []) + list(routes)) - {'*'}
        routes = {c: mode for c in caps}
        routes['image'] = image_provider
        changes = [('routing', routes), ('default_provider', mode)]
        if mode != 'local_qwen':
            changes.append(('deepseek_config', cfg))
        for key, value in changes:
            conn.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, store.encode(value)))
    return settings(capabilities)


def check_qwen_connection():
    """Passive gateway metadata; never load a model or acquire GPU capacity."""
    from .providers import LOCAL_QWEN
    try:
        with httpx.Client(timeout=5, headers={'X-VRAM-Wait-Seconds': '0'}) as client:
            response = client.get(LOCAL_QWEN['base_url'] + '/models')
            response.raise_for_status()
            available = {m['id'] for m in response.json()['data']}
            if LOCAL_QWEN['model'] not in available:
                return {'ok': False, 'message': '本機服務未列出 qwen3.8-27b，請檢查 VRAM Manager 的模型設定。'}
            vision = None
            try:
                props = client.get(LOCAL_QWEN['base_url'].removesuffix('/v1') + '/props')
                props.raise_for_status()
                vision = props.json().get('modalities', {}).get('vision')
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                pass  # Model may be unloaded; do not acquire GPU to probe.
        detail = '目前模型回報支援圖片理解。' if vision is True else '圖片理解狀態尚未確認。'
        return {'ok': True, 'model': LOCAL_QWEN['model'], 'vision': vision,
                'message': 'Qwen3.8 閘道已連線並列出所選模型。' + detail + '此檢查未生成內容；實際執行仍須取得 VRAM Manager 資源。'}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {'ok': False, 'message': '無法連接本機 Qwen3.8 閘道，請確認 VRAM Manager 服務後重試。'}


def check_connection():
    cfg = config()
    token = credential_value(cfg['key_env'])
    if not token:
        return {'ok': False, 'message': f"尚未設定 {cfg['key_env']}。請在啟動 Studio 的環境設定此變數，再重新啟動 Studio。"}
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get('https://api.deepseek.com/models', headers={'Authorization': f'Bearer {token}'})
            response.raise_for_status()
            available = {m['id'] for m in response.json()['data']}
        # DeepSeek continues accepting the retired V4 Flash names as aliases
        # for the current V4.1 Flash model. Compare canonical IDs so an older
        # saved profile does not report a false model outage.
        available = {LEGACY_MODEL_ALIASES.get(model, model) for model in available}
        selected = {LEGACY_MODEL_ALIASES.get(model, model) for model in (cfg['model'], cfg['vision_model'])}
        missing = selected - available
        if missing:
            return {'ok': False, 'message': '帳戶尚未提供所選模型：' + '、'.join(sorted(missing))}
        return {'ok': True, 'message': 'DeepSeek 已連線，文字與視覺模型可用。此檢查未提交生成工作。'}
    except httpx.HTTPStatusError as exc:
        return {'ok': False, 'message': f'DeepSeek 連線失敗（HTTP {exc.response.status_code}），請檢查憑證與帳戶權限。'}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {'ok': False, 'message': '無法確認 DeepSeek 連線，請檢查網路與 API 狀態後重試。'}
