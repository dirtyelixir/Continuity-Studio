"""No live GPU calls: exercise the existing manager admission protocol."""
import pytest
from studio import video_render as vr, comfy_video_provider as provider
from test_comfy_runtime import transport
from test_production import client


def test_prepare_switches_then_checks_under_reservation(monkeypatch):
    calls = transport(monkeypatch, mode='klein')
    def check():
        assert calls[-1][0] == '/vram/status'
        assert any(path == '/vram/gpu/acquire' for path, _ in calls)
        assert not any(path == '/vram/gpu/release' for path, _ in calls)
        return {'ready': True, 'mode': 'h3'}
    monkeypatch.setattr(provider, 'status', check)
    result = vr.prepare_provider()
    assert result['ready'] and '尚未開始生成' in result['message']
    assert calls[1] == ('/vram/comfy/mode', {'mode': 'h3'})
    assert calls[-1][0] == '/vram/gpu/release'


@pytest.mark.parametrize('paused,busy', [(True, False), (False, True)])
def test_prepare_cannot_override_manager_refusal(monkeypatch, paused, busy):
    calls = transport(monkeypatch, mode='klein', paused=paused, busy=busy)
    monkeypatch.setattr(provider, 'status', lambda: pytest.fail('must not check or submit after refusal'))
    with pytest.raises(ValueError):
        vr.prepare_provider()
    assert not any(path == '/vram/gpu/acquire' for path, _ in calls)


def test_missing_nodes_remain_not_ready_and_release(monkeypatch):
    calls = transport(monkeypatch, mode='h3')
    monkeypatch.setattr(provider, 'status', lambda: {'ready': False, 'message': 'missing nodes'})
    assert vr.prepare_provider() == {'ready': False, 'message': 'missing nodes'}
    assert not any(path == '/vram/comfy/mode' for path, _ in calls)
    assert calls[-1][0] == '/vram/gpu/release'


def test_get_is_passive_and_post_is_explicit_preparation(client, monkeypatch):
    from contextlib import contextmanager
    events = []
    @contextmanager
    def reserve(mode):
        events.append(('reserve', mode))
        yield
        events.append(('release', mode))
    monkeypatch.setattr(vr.comfy_runtime, 'reserve', reserve)
    monkeypatch.setattr(provider, 'status', lambda: {'ready': True})
    assert client.get('/api/video-provider/status').status_code == 200
    assert events == []
    result = client.post('/api/video-provider/prepare', json={})
    assert result.status_code == 200 and result.json()['ready']
    assert events == [('reserve', 'h3'), ('release', 'h3')]
