import copy
import json

import httpx
import pytest

from studio import comfy_runtime as runtime


def transport(monkeypatch, *, mode='h3', paused=False, busy=False, race=False):
    state = {'ok': True, 'paused': paused,
             'comfy_mode': {'running': mode, 'configured': mode, 'pid': 10},
             'comfy': {'ok': True, 'monitor_alive': True, 'pid': 10}}
    calls = []
    def handler(req):
        path = req.url.path
        body = json.loads(req.content) if req.content else {}
        calls.append((path, body))
        if path == '/vram/status':
            return httpx.Response(200, json=copy.deepcopy(state))
        if path == '/vram/comfy/mode':
            if busy:
                return httpx.Response(409, json={'ok': False, 'error': 'GPU busy'})
            state['comfy_mode'] = {'running': body['mode'], 'configured': body['mode'], 'pid': 11}
            state['comfy']['pid'] = 11
            return httpx.Response(200, json={'ok': True, 'ready': True, 'mode': body['mode']})
        if path == '/vram/gpu/acquire':
            assert body['workload'] == 'comfyui' and 0 < body['timeout'] <= 600 and body['pid'] > 0
            if race:
                state['comfy_mode']['running'] = 'h3'
            return httpx.Response(200, json={'ok': True, 'phase': 'granted'})
        if path == '/vram/gpu/release':
            return httpx.Response(200, json={'ok': True})
        raise AssertionError(path)
    client = httpx.Client
    monkeypatch.setattr(runtime.httpx, 'Client', lambda **kw: client(transport=httpx.MockTransport(handler), **kw))
    return calls


@pytest.mark.parametrize('wanted,initial', [('klein', 'h3'), ('h3', 'klein')])
def test_switch_and_reservation_both_directions(monkeypatch, wanted, initial):
    calls = transport(monkeypatch, mode=initial)
    with runtime.reserve(wanted) as evidence:
        assert evidence == {'mode': wanted, 'comfy_pid': 11, 'guarded': True}
        assert not any(p.endswith('/release') for p, _ in calls)
    assert [p for p, _ in calls] == ['/vram/status', '/vram/comfy/mode', '/vram/gpu/acquire', '/vram/status', '/vram/gpu/release']
    assert calls[2][1]['token'] == calls[-1][1]['token']


def test_same_mode_no_restart_and_release_on_failure(monkeypatch):
    calls = transport(monkeypatch, mode='klein')
    with pytest.raises(RuntimeError, match='render failed'):
        with runtime.reserve('klein'):
            raise RuntimeError('render failed')
    assert not any(p == '/vram/comfy/mode' for p, _ in calls)
    assert calls[-1][0] == '/vram/gpu/release'


@pytest.mark.parametrize('paused,busy', [(True, False), (False, True)])
def test_paused_or_busy_never_admits_work(monkeypatch, paused, busy):
    calls = transport(monkeypatch, paused=paused, busy=busy)
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        with runtime.reserve('klein'):
            pytest.fail('must not submit')
    assert not any(p == '/vram/gpu/acquire' for p, _ in calls)


def test_mode_change_between_switch_and_reservation_fails_closed(monkeypatch):
    calls = transport(monkeypatch, race=True)
    with pytest.raises(ValueError, match='不一致'):
        with runtime.reserve('klein'):
            pytest.fail('must not submit')
    assert calls[-1][0] == '/vram/gpu/release'
