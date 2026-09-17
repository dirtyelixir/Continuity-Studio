"""Read-only detection of a dead local ComfyUI executor despite a live HTTP server.

The installed arbiter monitors HTTP/leases, not prompt_worker. A thread traceback
from this exact process is positive evidence; missing logs or slow work are not.
No service, GPU lease or external file is changed here.
"""
import os
import re
import subprocess
from pathlib import Path

DEAD_WORKER = re.compile(r'Exception in thread [^\r\n]*\(prompt_worker\):')


def worker_failure(pid):
    if type(pid) is not int or pid <= 0:
        return None
    try:
        proc = Path('/proc') / str(pid)
        # Never accept a remote/reused PID or an unrelated local service log.
        args = (proc / 'cmdline').read_bytes().split(b'\0')
        if b'main.py' not in args or (proc / 'cwd').resolve().name != 'ComfyUI':
            return None
        ticks = int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[19])
        boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime '))
        since = boot + ticks / os.sysconf('SC_CLK_TCK')
        log = subprocess.run(['journalctl', '--user', '-b', '_PID=' + str(pid),
                              '--since=@' + str(int(since)), '-n', '500', '--no-pager', '-o', 'cat'],
                             capture_output=True, text=True, timeout=3)
        if log.returncode == 0 and DEAD_WORKER.search(log.stdout):
            return {'kind': 'executor_stopped', 'pid': pid, 'source': 'local_process_journal',
                    'message': 'ComfyUI 圖片執行緒已停止，但網頁服務仍在線；已停止等待並保留工作回條。請先修復本機出圖服務，再取回原工作結果或重新生成。'}
    except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired):
        pass
    return None
