import copy
import json

import httpx
import pytest
from PIL import Image

from studio import providers, provider_profiles as profiles, store, engine, models, context_limits
from test_production import client, plan, create


def test_qwen_profile_routes_and_preserves_existing_work(client, plan, monkeypatch):
    pid = create(client, plan)
    before = copy.deepcopy(store.project(pid))
    profiles.apply('deepseek', model='deepseek-flash')
    cfg = store.setting('deepseek_config')
    store.put_setting('routing', {'old_skill': 'manual'})
    monkeypatch.setattr(profiles, 'save_credential', lambda *a: pytest.fail('Credential write'))
    result = client.post('/api/settings/profile', json={'mode': 'local_qwen', 'image_provider': 'comfy_local', 'api_key': 'ignored-test-value'})
    assert result.status_code == 200, result.text
    assert result.json()['mode'] == 'local_qwen'
    assert store.setting('deepseek_config') == cfg
    for capability in providers.BUILTINS + ['old_skill', 'future_skill', 'chapter_outline']:
        assert providers.resolve(capability)['id'] == ('comfy_local' if capability == 'image' else 'local_qwen')
    monkeypatch.setattr(engine.POOL, 'submit', lambda *a: None)
    freeze = context_limits.freeze
    monkeypatch.setattr(context_limits, 'freeze', lambda p, **kw: freeze(p, probe=False))
    job = engine.enqueue(pid, models.JobRequest(capability='qc'))['job']
    frozen = copy.deepcopy(store.job(job['id']))
    assert frozen['input']['provider_config']['model'] == 'qwen3.8-27b'
    client.post('/api/settings/routing', json={'capability': 'qc', 'provider_id': 'astra'})
    assert client.get('/api/settings').json()['profile']['mode'] == 'custom'
    assert client.post('/api/settings/profile', json={'mode': 'astra'}).json()['mode'] == 'astra'
    assert providers.resolve('future_skill')['id'] == 'astra'
    assert store.job(job['id']) == frozen
    assert store.project(pid) == before


def test_qwen_cannot_render_even_with_wildcard(client, monkeypatch, tmp_path):
    assert not providers.supports(providers.LOCAL_QWEN, 'image')
    assert client.post('/api/settings/routing', json={'capability': 'image', 'provider_id': 'local_qwen'}).status_code == 400
    before = client.get('/api/settings').json()['profile']
    assert client.post('/api/settings/profile', json={'mode': 'local_qwen', 'image_provider': 'local_qwen'}).status_code == 400
    assert client.get('/api/settings').json()['profile'] == before
    monkeypatch.setattr(providers, 'http_run', lambda *a: pytest.fail('Image network call'))
    with pytest.raises(ValueError, match='圖片生成'):
        providers.run(providers.LOCAL_QWEN, 'image', 'test', [], tmp_path)


def transport(monkeypatch, handler):
    real = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.parametrize('scenario', ['ready', 'unloaded', 'missing', 'offline'])
def test_passive_connection_check(client, monkeypatch, scenario):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'GET'
        assert request.headers['X-VRAM-Wait-Seconds'] == '0'
        if scenario == 'offline':
            raise httpx.ConnectError('test-only offline')
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [] if scenario == 'missing' else [{'id': 'qwen3.8-27b'}]})
        assert request.url.path == '/props'
        return httpx.Response(503 if scenario == 'unloaded' else 200, json={'modalities': {'vision': True}})
    transport(monkeypatch, handler)
    result = client.post('/api/settings/qwen/check', json={}).json()
    assert result['ok'] == (scenario in ('ready', 'unloaded'))
    if scenario == 'ready':
        assert result['vision'] is True
    if scenario == 'unloaded':
        assert result['vision'] is None
    assert seen


@pytest.mark.parametrize('count', [0, 2])
def test_qwen_real_adapter_text_and_image_payload(client, monkeypatch, tmp_path, count):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url == 'http://127.0.0.1:8080/v1/chat/completions'
        assert request.headers['X-VRAM-Wait-Seconds'] == '0'
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"text":"fixture direction"}'}, 'finish_reason': 'stop'}]})
    transport(monkeypatch, handler)
    refs = []
    for n in range(count):
        path = tmp_path / f'{n}.png'
        Image.new('RGB', (8, 8), 'red').save(path)
        refs.append(path)
    assert providers.run(providers.LOCAL_QWEN, 'h3', 'test-only prompt', refs, tmp_path / 'job')['text'] == 'fixture direction'
    payload = json.loads(seen[0].content)
    assert payload['model'] == 'qwen3.8-27b'
    content = payload['messages'][0]['content']
    assert isinstance(content, list if count else str)
    if count:
        assert len(content) == count + 1
        assert all(x['image_url']['url'].startswith('data:image/png;base64,') for x in content[1:])


@pytest.mark.parametrize('status,content,finish', [(503, '', 'stop'), (200, '', 'stop'), (200, '{}', 'stop'), (200, '{"text":"partial"}', 'length')])
def test_qwen_failure_never_falls_back(client, monkeypatch, tmp_path, status, content, finish):
    transport(monkeypatch, lambda r: httpx.Response(status, json={'choices': [{'message': {'content': content}, 'finish_reason': finish}]}))
    monkeypatch.setattr(providers, 'codex_run', lambda *a: pytest.fail('Fallback forbidden'))
    with pytest.raises((RuntimeError, ValueError)):
        providers.run(providers.LOCAL_QWEN, 'h3', 'test', [], tmp_path)


def warm_transport(monkeypatch, warm_status, chat_statuses):
    """Serve the manager's warm endpoint and a scripted sequence of chat responses."""
    seen = []
    chats = list(chat_statuses)

    def handler(request):
        seen.append(str(request.url))
        if request.url.path == '/vram/qwen/warm':
            assert request.method == 'POST'
            return httpx.Response(warm_status, json={'ok': warm_status == 200})
        assert request.url.path == '/v1/chat/completions'
        status = chats.pop(0) if chats else 503
        return httpx.Response(status, json={'choices': [{'message': {'content': '{"text":"after warm"}'}, 'finish_reason': 'stop'}]})

    real = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    return seen


def test_qwen_warms_then_retries_once_without_substitution(client, monkeypatch, tmp_path):
    """A 503 from an unloaded Qwen is a load race: warm via the manager, retry once, same provider."""
    seen = warm_transport(monkeypatch, 200, [503, 200])
    monkeypatch.setattr(providers, 'codex_run', lambda *a: pytest.fail('Fallback forbidden'))
    result = providers.run(providers.LOCAL_QWEN, 'h3', 'test-only prompt', [], tmp_path / 'job')
    assert result['text'] == 'after warm'
    assert sum('/vram/qwen/warm' in u for u in seen) == 1, seen
    assert sum('/v1/chat/completions' in u for u in seen) == 2, seen
    receipt = json.loads((tmp_path / 'job' / 'qwen-warm.json').read_text())
    assert receipt['ready'] is True and receipt['timeout'] == providers.QWEN_WARM_TIMEOUT


def test_qwen_does_not_retry_forever_when_warm_fails(client, monkeypatch, tmp_path):
    """If the manager cannot load Qwen, report honestly after ONE retry - never loop or substitute."""
    seen = warm_transport(monkeypatch, 409, [503, 503, 503])
    monkeypatch.setattr(providers, 'codex_run', lambda *a: pytest.fail('Fallback forbidden'))
    with pytest.raises(RuntimeError, match='忙碌或暫時不可用'):
        providers.run(providers.LOCAL_QWEN, 'h3', 'test', [], tmp_path / 'job')
    # One warm attempt, at most two chat attempts (original + single retry).
    assert sum('/vram/qwen/warm' in u for u in seen) == 1, seen
    assert sum('/v1/chat/completions' in u for u in seen) <= 2, seen
    receipt = json.loads((tmp_path / 'job' / 'qwen-warm.json').read_text())
    assert receipt['ready'] is False and receipt['status'] == 409


def test_non_qwen_providers_never_call_the_manager_warm(client, monkeypatch, tmp_path):
    """Only local_qwen has a manager-managed lifecycle; other HTTP providers must not warm."""
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(503, json={'error': 'busy'})

    real = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    provider = {**providers.LOCAL_QWEN, 'id': 'other_http', 'base_url': 'http://other.invalid/v1'}
    # An ordinary HTTP provider surfaces the transport status error; only local_qwen has
    # a manager-managed lifecycle, so no warm attempt is made for it.
    with pytest.raises(httpx.HTTPStatusError):
        providers.run(provider, 'h3', 'test', [], tmp_path / 'job')
    assert not any('/vram/qwen/warm' in u for u in seen), seen
    assert not (tmp_path / 'job' / 'qwen-warm.json').exists()
