"""Select the installed runtime through VRAM Manager and pin it during a job."""
import logging
import os
import time
import uuid
from contextlib import contextmanager

import httpx


class AdmissionBusy(ValueError):
    """Manager explicitly refused before acquiring or switching; safe to wait."""


def manager_url():
    return os.environ.get('STUDIO_VRAM_URL', 'http://127.0.0.1:8082').rstrip('/')


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code == 409:
        reason = str(response.json().get('error', 'GPU 忙碌'))
        # Exact, endpoint-specific pre-admission responses only. Transport errors,
        # cancelled admissions and failures after a mode switch are not retryable.
        busy = (path == '/vram/gpu/acquire' and reason == 'GPU busy; timed out waiting for its current owner'
                or path == '/vram/comfy/mode' and reason in (
                    '有工作／預約；請等工作完成再啟動或切換',
                    'ComfyUI 有生成／排隊／提交中工作，未有切換模式'))
        raise (AdmissionBusy if busy else ValueError)('VRAM Manager 未允許操作：' + reason)
    response.raise_for_status()
    body = response.json()
    if not body.get('ok'):
        raise ValueError(body.get('error') or 'VRAM Manager 未確認操作。')
    return body


def status(client, *, wait_seconds=180):
    deadline = time.monotonic() + wait_seconds
    while True:
        state = request(client, 'GET', '/vram/status')
        if state.get('paused'):
            raise ValueError('VRAM Manager 已暫停接收工作；請先恢復接收，尚未送出生成。')
        if not state.get('maintenance') and not state.get('transition'):
            return state
        if time.monotonic() >= deadline:
            raise ValueError('等待 VRAM Manager 切換完成逾時；尚未送出生成，請稍後重試。')
        time.sleep(min(1, max(0, deadline - time.monotonic())))


@contextmanager
def reserve(mode, *, wait_seconds=600):
    if mode not in ('klein', 'h3'):
        raise ValueError('未知 ComfyUI 執行模式。')
    token = 'studio-mode-' + uuid.uuid4().hex
    with httpx.Client(base_url=manager_url(), timeout=190, trust_env=False) as client:
        state = status(client)
        runtime = state.get('comfy_mode', {})
        if runtime.get('running') != mode or runtime.get('configured') != mode:
            # The manager atomically refuses active/queued GPU work, protects
            # custom launchers and verifies the replacement process before return.
            switched = request(client, 'POST', '/vram/comfy/mode', json={'mode': mode})
            if not switched.get('ready') or switched.get('mode') != mode:
                raise ValueError('ComfyUI 模式切換未確認，尚未送出生成。')
        try:
            # ComfyUI's own lease can join this outer reservation. This closes
            # the switch-versus-submit race without changing any GPU service.
            request(client, 'POST', '/vram/gpu/acquire', json={
                'token': token, 'workload': 'comfyui', 'pid': os.getpid(), 'timeout': wait_seconds},
                timeout=wait_seconds + 190)
            state = status(client)
            runtime = state.get('comfy_mode', {})
            comfy = state.get('comfy', {})
            if (runtime.get('running') != mode or runtime.get('configured') != mode
                    or not runtime.get('pid') or runtime['pid'] != comfy.get('pid')
                    or not comfy.get('ok') or not comfy.get('monitor_alive')
                    or comfy.get('last_error')):
                raise ValueError('ComfyUI 實際程序與所需模式不一致，尚未送出生成。')
            yield {'mode': mode, 'comfy_pid': runtime['pid'], 'guarded': True}
        finally:
            try:
                request(client, 'POST', '/vram/gpu/release', json={'token': token}, timeout=5)
            except (httpx.HTTPError, ValueError):
                logging.exception('VRAM Manager reservation release failed: %s', token)
