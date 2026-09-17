import pytest
from studio import comfy_runtime as runtime


def clock(monkeypatch):
    now = [0.0]
    sleeps = []
    monkeypatch.setattr(runtime.time, 'monotonic', lambda: now[0])
    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay
    monkeypatch.setattr(runtime.time, 'sleep', sleep)
    return sleeps


def test_waits_for_transition_and_maintenance_without_writes(monkeypatch):
    sleeps = clock(monkeypatch)
    states = iter([{'transition': 'switching_comfy_mode', 'maintenance': True},
                   {'transition': 'starting_qwen'}, {'maintenance': True},
                   {'paused': False, 'transition': None, 'comfy_mode': {'running': 'h3'}}])
    calls = []
    def request(c, method, path):
        calls.append((method, path))
        return next(states)
    monkeypatch.setattr(runtime, 'request', request)
    assert runtime.status(None)['comfy_mode']['running'] == 'h3'
    assert sleeps == [1, 1, 1]
    assert calls == [('GET', '/vram/status')] * 4


def test_pause_during_switch_stops_without_unpausing(monkeypatch):
    sleeps = clock(monkeypatch)
    states = iter([{'transition': 'switching_comfy_mode'}, {'paused': True, 'transition': 'releasing_now'}])
    monkeypatch.setattr(runtime, 'request', lambda *a: next(states))
    with pytest.raises(ValueError, match='已暫停接收'):
        runtime.status(None)
    assert sleeps == [1]


def test_transition_wait_has_deadline(monkeypatch):
    sleeps = clock(monkeypatch)
    monkeypatch.setattr(runtime, 'request', lambda *a: {'transition': 'stuck'})
    with pytest.raises(ValueError, match='切換完成逾時'):
        runtime.status(None, wait_seconds=2)
    assert sum(sleeps) == 2


def test_post_reservation_transition_still_checks_actual_mode(monkeypatch):
    from test_comfy_runtime import transport
    calls = transport(monkeypatch, mode='h3')
    with runtime.reserve('h3') as evidence:
        assert evidence['mode'] == 'h3'
    assert not any(path == '/vram/comfy/mode' for path, _ in calls)
    assert calls[-1][0] == '/vram/gpu/release'
