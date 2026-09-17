"""Read-only progress from saved proposal and canonical verification artifacts."""
import json
from . import store


def _read(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _mtime(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def progress(job):
    if job['capability'] not in ('narrative', 'storyboard') or job['state'] != 'running':
        return None
    work = store.DATA / 'jobs' / job['id']
    result = {'kind': 'proposal_validation',
              'label': '正在生成故事與製作方案，尚未有已保存結果。'}
    path = work / 'result.json'
    if job['capability'] == 'storyboard' and (work / 'repair-1/result.json').is_file():
        path = work / 'repair-1/result.json'
    raw = _read(path)
    if raw is None:
        return result
    plan = raw.get('production', raw)
    shots = plan.get('shots') if isinstance(plan, dict) else None
    if not isinstance(shots, list):
        result['label'] = '已保存服務商輸出，正在驗證方案格式。'
        return result
    ids = {s['id'] for s in shots if isinstance(s, dict) and isinstance(s.get('id'), str)}
    result.update(completed_shots=0, total_shots=len(shots),
                  label='故事與製作方案已保存，正在準備鏡頭狀態驗證。')
    # A complete compiled artifact is written only after prepare_plan returns.
    compiled = _read(work / 'canonical-production.json')
    if compiled is not None and isinstance(compiled.get('shots'), list):
        compiled_ids = {s.get('id') for s in compiled['shots'] if isinstance(s, dict)}
        if compiled_ids == ids and len(compiled['shots']) == len(shots):
            result.update(completed_shots=len(shots), label='各鏡頭狀態驗證已完成，正在保存方案及安排後續審查。')
            return result
    latest = {}
    for source_path in (work / 'canonical-state').glob('*/source.json'):
        source = _read(source_path) or {}
        shot = source.get('shot')
        sid = shot.get('id') if isinstance(shot, dict) else None
        if sid not in ids:
            continue
        folder = source_path.parent
        receipt = _read(folder / 'receipt.json') or {}
        stamp = max(_mtime(source_path), _mtime(folder / 'receipt.json'))
        if sid not in latest or stamp > latest[sid][0]:
            latest[sid] = (stamp, folder, receipt)
    completed = sum(item[2].get('state') == 'accepted' for item in latest.values())
    result['completed_shots'] = completed
    pending = [(sid, item) for sid, item in latest.items() if item[2].get('state') != 'accepted']
    prefix = '方案已保存；'
    recoveries = [_read(p) or {} for p in (work / 'recovery-attempts').glob('*/receipt.json')]
    if any(r.get('state') == 'running' for r in recoveries):
        prefix = '正在恢復已保存方案；'
    if pending:
        sid, (_, folder, receipt) = max(pending, key=lambda item: item[1][0])
        result['current_shot_id'] = sid
        if receipt.get('state') in ('blocked', 'failed'):
            stage = '最近保存的鏡頭驗證未通過，正在處理恢復或記錄結果'
        elif (folder / 'check/request.txt').is_file():
            stage = '正在獨立核對鏡頭狀態與劇情'
        elif (folder / 'extract-repair/request.txt').is_file():
            stage = '正在修正鏡頭狀態格式'
        else:
            stage = '正在整理鏡頭狀態'
        result['label'] = f'{prefix}{stage}（{sid}，已通過 {completed}／{len(shots)} 鏡）。'
    elif completed:
        result['label'] = f'{prefix}鏡頭狀態已通過 {completed}／{len(shots)} 鏡，正在接續驗證及保存。'
    return result
