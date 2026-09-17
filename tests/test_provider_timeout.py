"""Timeout diagnostics must not equate retained logs with a recoverable result."""
import signal
import subprocess
import sys

import pytest

from studio import providers


@pytest.mark.parametrize('saved', [None, b'', b'{"text":"saved"}', b'{"text":'])
@pytest.mark.parametrize('cancelled', [False, True])
def test_timeout_reports_actual_output_and_preserves_it(tmp_path, monkeypatch, saved, cancelled):
    work = tmp_path / 'job'
    work.mkdir()
    if cancelled:
        (work / 'cancel-requested').touch()
    signals = []
    calls = []

    class Process:
        pid = 12345

        def __init__(self, cmd, **kwargs):
            assert kwargs['start_new_session']
            calls.append(cmd)
            # Simulate the child writing an output before timing out.
            if saved is not None:
                (work / 'result.json').write_bytes(saved)

        def communicate(self, *args, **kwargs):
            raise subprocess.TimeoutExpired('codex', 1)

        def wait(self, timeout):
            return 0

    ticks = iter([0, 1201])
    monkeypatch.setattr(providers.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(providers.shutil, 'which', lambda _: '/mock/codex')
    monkeypatch.setattr(providers.subprocess, 'Popen', Process)
    monkeypatch.setattr(providers.os, 'killpg', lambda pid, sig: signals.append((pid, sig)))
    with pytest.raises(RuntimeError) as error:
        providers.codex_run(providers.DEFAULT, 'h3', 'test-only request', [], work)
    message = str(error.value)
    if cancelled:
        assert message == '使用者已取消工作。'
    elif saved:
        assert 'A result file was retained; validate it before recovery.' in message
    else:
        assert 'No structured result was saved' in message
    assert len(calls) == 1  # No automatic resubmission.
    assert signals == [(12345, signal.SIGTERM)]
    assert (work / 'request.txt').read_text() == 'test-only request'
    if saved is None:
        assert not (work / 'result.json').exists()
    else:
        assert (work / 'result.json').read_bytes() == saved


def test_large_request_reaches_slow_child_intact(tmp_path, monkeypatch):
    """Regression: repeated communicate(None) previously stranded a partial pipe."""
    import hashlib
    import json
    real_popen = subprocess.Popen
    prompt = '長章節完整內容\n' * 30000
    work = tmp_path / 'slow-child'
    # Real subprocess, larger than pipe capacity, reads after the first poll expires.
    child = '''import sys,time,json,hashlib
from pathlib import Path
time.sleep(1.2)
data=sys.stdin.buffer.read()
Path(sys.argv[1]).write_text(json.dumps({'text':hashlib.sha256(data).hexdigest()}))
'''
    def spawn(cmd, **kwargs):
        assert kwargs['stdin'].readable()
        return real_popen([sys.executable, '-c', child, str(work/'result.json')], **kwargs)
    monkeypatch.setattr(providers.shutil, 'which', lambda _: '/mock/codex')
    monkeypatch.setattr(providers.subprocess, 'Popen', spawn)
    # Bound regressions without a 20-minute hung test.
    original = providers.time.monotonic
    start = original()
    monkeypatch.setattr(providers.time, 'monotonic', lambda: 1201 if original()-start>4 else original()-start)
    result = providers.codex_run(providers.DEFAULT, 'h3', prompt, [], work)
    assert result['text'] == hashlib.sha256(prompt.encode()).hexdigest()
