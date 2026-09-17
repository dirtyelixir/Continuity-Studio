"""Read-only preview of retained, unaccepted production output."""
import json
from . import store


def _read(path):
    try:
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) else None
    except (OSError,ValueError):
        return None


def preview(job):
    if job['capability'] not in ('narrative','storyboard') or job['state'] not in ('failed','interrupted'):
        return None
    work=store.DATA/'jobs'/job['id']
    path=work/'result.json'
    if job['capability']=='storyboard' and (work/'repair-1/result.json').is_file():
        path=work/'repair-1/result.json'
    raw=_read(path)
    if raw is None:return None
    plan=raw.get('production',raw)
    if not isinstance(plan,dict):return None
    result={k:plan.get(k,'') if isinstance(plan.get(k,''),str) else '' for k in ('title','story','screenplay')}
    result.update({k:len(plan[k]) if isinstance(plan.get(k),list) else 0 for k in ('canon','scenes','shots')})
    checks={}
    for path in sorted((work/'canonical-state').glob('*/receipt.json'),key=lambda p:p.stat().st_mtime):
        receipt=_read(path) or {}
        source=_read(path.parent/'source.json') or {}
        shot=source.get('shot') or {}
        shot_id=shot.get('id','') if isinstance(shot,dict) else ''
        checks[shot_id or path.parent.name]={'shot_id':shot_id,
            'state':receipt.get('state','unknown'),'error':receipt.get('error','')}
    result['checks']=list(checks.values())
    return result
