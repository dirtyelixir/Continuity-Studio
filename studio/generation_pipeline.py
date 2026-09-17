"""Adaptive generation planning over complete source units, with durable assembly.

Local plans are provisional. Every artificial split is reconciled at its boundary
before the aggregate can be saved or adopted. No partial provider output is used.
"""
import copy
import json
from pathlib import Path

from . import context_limits as limits, generation_groups as groups, providers, store
from .chapter_pipeline import atomic_json as atomic

VERSION = 'generation-stages-v1'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def schema(provider):
    value = groups.GroupPlan.model_json_schema()
    return providers.strict_schema(value) if provider['kind'] == 'codex' else value


def scope(source, ids):
    """Partition by edit use, keeping complete original shots and scene direction."""
    value = copy.deepcopy(source)
    production = value['production']
    if list(ids) == [e['id'] for e in production['edit_plan']]:
        return value  # Keep the complete original single-request contract.
    production['edit_plan'] = [e for e in production['edit_plan'] if e['id'] in ids]
    shot_ids = {e['shot_id'] for e in production['edit_plan']}
    production['shots'] = [s for s in production['shots'] if s['id'] in shot_ids]
    if 'source_conditioning' in value:
        value['source_conditioning'] = {k:v for k,v in value['source_conditioning'].items() if k in shot_ids}
    entities = {e for s in production['shots'] for e in s['entity_ids']}
    entities.update(s['location_id'] for s in production['scenes'])
    production['canon'] = [e for e in production['canon'] if e['id'] in entities]
    frames = {f['id'] for s in production['shots'] for f in s['keyframes']}
    value['frame_readiness'] = {k:v for k,v in value.get('frame_readiness', {}).items() if k in frames}
    value['storyboard_reviewed_frames'] = [f for f in value.get('storyboard_reviewed_frames', []) if f in frames]
    value['storyboard_intent'] = [r for r in value.get('storyboard_intent', []) if r['edit_id'] in ids]
    value['edit_positions'] = {k:v for k,v in value['edit_positions'].items() if k in ids}
    return value


def boundary_projection(source):
    """Boundary phase has original timing/state plus complete local decisions.

    Full keyframe descriptions and within-shot craft were read in mandatory local
    calls. Retain every board image-use intent and every source frame's timestamp.
    This projection is explicit in the request and never alters validation source.
    """
    value = copy.deepcopy(source)
    for shot in value['production']['shots']:
        shot['keyframes'] = [{k:f[k] for k in ('id','moment','source_time','state') if k in f} for f in shot['keyframes']]
    return value


def summary(items):
    native = sum(g['execution'] == 'native_montage' for g in items)
    return f'已完成分批規劃及交界核對：{native} 個多鏡分組、{len(items)-native} 個獨立來源。各項理由、成片檢查及逐張用圖決定完整保留。'


class Planner:
    def __init__(self, job, work):
        self.job, self.work = job, Path(work)
        self.inp = job['input']
        if self.inp.get('generation_pipeline') != VERSION:
            raise ValueError('未知生成安排階段版本；請建立新工作。')
        self.source = self.inp['group_plan_source']
        self.provider = self.inp['provider_config']
        self.policy = self.provider['context_policy']
        self.schema = schema(self.provider)
        if self.inp.get('schema') != providers.strict_schema(groups.GroupPlan.model_json_schema()):
            raise ValueError('生成安排格式已更新；請建立新工作，舊成果保留。')
        self.identity = store.digest([VERSION, self.inp, self.schema])
        original = encode(self.source)
        if self.inp['prompt'].count(original) != 1:
            raise ValueError('未能辨識完整生成安排來源；請建立新工作。')
        self.prefix, self.suffix = self.inp['prompt'].split(original, 1)
        self.ids = [e['id'] for e in self.source['production']['edit_plan']]
        self.counts = {}

    def cancel(self):
        if (self.work/'cancel-requested').exists():
            raise RuntimeError('使用者已取消工作。')

    def task(self, key, ids, phase='local', candidates=None, projected=False):
        selected = scope(self.source, ids)
        supplied = boundary_projection(selected) if projected else selected
        prompt = self.prefix + encode(supplied) + self.suffix
        if ids != self.ids or phase != 'local':
            order = [[e['id'], e['shot_id'], e['planned_edit_in'], e['planned_edit_out']]
                     for e in self.source['production']['edit_plan']]
            prompt += '\nADAPTIVE PHASE CONTRACT:\n' + encode({
                'phase': phase, 'requested_edit_ids': ids, 'complete_edit_order': order,
                'rules': 'Cover ONLY requested_edit_ids exactly once in their original order. Source shots and scene direction are original, not summaries. Every other source is covered by another mandatory phase. Never claim missing pixels are approved. Output concise reasons/checks; no duplicated explanatory prose.',
                'boundary_rules': ('The two completed local groups are provisional. Replan their complete edit interval together: merge, repartition or retain them according to visual/editorial needs, never because they came from different model batches. Other groups are fixed. Local phases already read complete source shots and keyframes; this boundary phase owns grouping across the artificial split. '+
                                   ('This request omits only source keyframe descriptions already assessed in the complete local calls; all board-image intent, source states, action, dialogue, sound, timing and local decisions are supplied.' if projected else 'Complete selected source shots are supplied.')) if phase == 'boundary' else '',
                'provisional_groups': candidates or [],
            })
        return {'key':key, 'ids':ids, 'phase':phase, 'projected':projected,
                'prompt':prompt, 'fingerprint':store.digest([self.identity,key,ids,phase,projected,prompt])}

    def fits(self, task, output_hint=True):
        self.cancel()
        digest = store.digest(task['prompt'])
        if digest not in self.counts:
            self.counts[digest] = limits.count(self.provider, task['prompt'], self.schema, self.policy)
        count = self.counts[digest]
        receipt = {'policy':self.policy,'input_tokens':count,
                   'count_method':'chat-template-tokenizer' if self.policy['tokenizer']=='llama_cpp' else 'utf8-byte-upper-bound',
                   'fits':limits.fits(count,self.policy)}
        atomic(self.work/(task['key']+'-preflight.json'), {'fingerprint':task['fingerprint'],**receipt})
        if task['key']=='root':
            atomic(self.work/'context-budget.json',receipt)
        # A batching hint, not a promise about reasoning/output usage.
        anchors = sum(r['edit_id'] in task['ids'] for r in self.source.get('storyboard_intent', []))
        output = 800 + 900*len(task['ids']) + 400*anchors
        return limits.fits(count, self.policy) and (not output_hint or output <= self.policy['max_output_tokens'])

    def validated(self, ids, value):
        return groups.validate_plan(value, scope(self.source, ids))

    def call(self, task):
        self.cancel()
        path = self.work/(task['key']+'-checkpoint.json')
        if path.exists():
            saved = json.loads(path.read_text())
            if saved['fingerprint'] != task['fingerprint'] or saved['result_hash'] != store.digest(saved['result']):
                raise ValueError('已保存批次與凍結來源不符；不能混用成果。')
            return self.validated(task['ids'], saved['result'])
        completed = len(list(self.work.glob('*-checkpoint.json')))
        atomic(self.work/'generation-progress.json', {'kind':'generation_stages','label':
               ('正在核對分批交界' if task['phase']=='boundary' else '正在安排分鏡')+f' · {len(task["ids"])} 項',
               'completed':completed,'total':None})
        attempts = sorted(self.work.glob(task['key']+'-attempt-*'))
        for previous in reversed(attempts):
            meta = json.loads((previous/'identity.json').read_text())
            if meta['fingerprint'] != task['fingerprint']:
                raise ValueError('批次嘗試來源不符；請建立新工作。')
            if self.exhausted(previous):
                raise OutputExhausted()
            raw = previous/'result.json'
            if raw.exists():
                try:
                    result = self.validated(task['ids'], json.loads(raw.read_text()))
                except ValueError:
                    continue
                self.cancel()
                atomic(path, {'fingerprint':task['fingerprint'],'result_hash':store.digest(result),'result':result})
                return result
        attempt = self.work/(task['key']+f'-attempt-{len(attempts)+1:03d}')
        attempt.mkdir()
        atomic(attempt/'identity.json', {'fingerprint':task['fingerprint']})
        (attempt/'request.txt').write_text(task['prompt'])
        limits.check(self.provider, task['prompt'], self.schema, attempt)
        try:
            result = providers.run(self.provider, 'h3_group_plan', task['prompt'], [], attempt)
        except Exception:
            if self.exhausted(attempt):
                raise OutputExhausted() from None
            raise  # Ambiguous/transport errors never trigger automatic re-submission.
        if self.exhausted(attempt):
            raise OutputExhausted()
        result = self.validated(task['ids'], result)
        self.cancel()
        atomic(path, {'fingerprint':task['fingerprint'],'result_hash':store.digest(result),'result':result})
        return result

    @staticmethod
    def exhausted(attempt):
        try:
            return json.loads((attempt/'transport.json').read_text()).get('finish_reason') == 'length'
        except (OSError, ValueError):
            return False

    def boundary(self, key, left, right, replay=False, projected=False):
        candidates = [left[-1],right[0]]
        ids = [eid for g in candidates for eid in g['edit_ids']]
        task = self.task(key, ids, 'boundary', candidates, projected)
        if not replay and not self.fits(task, output_hint=False):
            projected = True
            task = self.task(key, ids, 'boundary', candidates, projected)
            if not self.fits(task, output_hint=False):
                raise ValueError('最小分組交界仍超出模型容量；已保存各批安排。請提高所選模型容量後建立新工作。')
        try:
            result = self.read_call(task) if replay else self.call(task)
        except OutputExhausted:
            raise ValueError('分組交界輸出仍超出預算；各批成果已保存，請提高所選模型輸出預留。') from None
        return left[:-1]+result['groups']+right[1:], projected

    def read_call(self, task):
        saved = json.loads((self.work/(task['key']+'-checkpoint.json')).read_text())
        if saved['fingerprint'] != task['fingerprint'] or saved['result_hash'] != store.digest(saved['result']):
            raise ValueError('生成安排批次驗證失敗。')
        return self.validated(task['ids'], saved['result'])

    def replay(self, key, ids):
        record = json.loads((self.work/(key+'-node.json')).read_text())
        if record['identity'] != self.identity or record['ids'] != ids:
            raise ValueError('生成安排組合來源不符。')
        if record['kind'] == 'leaf':
            result = self.read_call(self.task(key, ids))
        elif record['kind'] == 'split' and len(ids)>1:
            half = len(ids)//2
            left = self.replay(key+'L', ids[:half])['groups']
            right = self.replay(key+'R', ids[half:])['groups']
            items, _ = self.boundary(key+'B', left, right, replay=True, projected=record['projected'])
            result = self.validated(ids, {'summary':summary(items),'groups':items})
        else:
            raise ValueError('生成安排組合記錄不完整。')
        if record['result_hash'] != store.digest(result):
            raise ValueError('生成安排組合內容不符。')
        return result

    def solve(self, key, ids):
        self.cancel()
        node = self.work/(key+'-node.json')
        if node.exists():
            return self.replay(key, ids)
        task = self.task(key, ids)
        split = self.work/(key+'-split.json')
        if split.exists():
            if json.loads(split.read_text()) != {'identity':self.identity,'ids':ids}:
                raise ValueError('分批記錄與原始工作不符。')
        elif self.fits(task, output_hint=len(ids)>1):
            try:
                result = self.call(task)
            except OutputExhausted:
                if len(ids)==1:
                    raise ValueError('單一來源輸出仍超出預算；原文保留，請提高所選模型輸出預留。') from None
            else:
                atomic(node, {'identity':self.identity,'ids':ids,'kind':'leaf','result_hash':store.digest(result)})
                return result
        if len(ids)==1:
            raise ValueError('單一完整分鏡及必要指示仍超出模型容量；原文保留，請提高所選模型容量或修訂上游分鏡。')
        atomic(split, {'identity':self.identity,'ids':ids})
        half = len(ids)//2
        left = self.solve(key+'L', ids[:half])['groups']
        right = self.solve(key+'R', ids[half:])['groups']
        self.cancel()
        items, projected = self.boundary(key+'B', left, right)
        result = self.validated(ids, {'summary':summary(items),'groups':items})
        atomic(node, {'identity':self.identity,'ids':ids,'kind':'split','projected':projected,'result_hash':store.digest(result)})
        return result


class OutputExhausted(Exception):
    pass


def run(job, work):
    runner = Planner(job, work)
    runner.work.mkdir(parents=True, exist_ok=True)
    runner.cancel()
    manifest = runner.work/'generation-manifest.json'
    record = {'version':VERSION,'identity':runner.identity,'edit_ids':runner.ids}
    if manifest.exists() and json.loads(manifest.read_text()) != record:
        raise ValueError('分批安排與凍結來源或模型設定不符。')
    atomic(manifest, record)
    result = runner.solve('root', runner.ids)
    runner.cancel()
    result = groups.validate_plan(result, runner.source)
    atomic(runner.work/'result.json', result)
    atomic(runner.work/'generation-complete.json', {'identity':runner.identity,'result_hash':store.digest(result)})
    count = len(list(runner.work.glob('*-checkpoint.json')))
    atomic(runner.work/'generation-progress.json', {'kind':'generation_stages','label':'生成安排已完成','completed':count,'total':count})
    return result


def require_complete(job, result):
    try:
        runner = Planner(job, store.DATA/'jobs'/job['id'])
        manifest = json.loads((runner.work/'generation-manifest.json').read_text())
        assert manifest == {'version':VERSION,'identity':runner.identity,'edit_ids':runner.ids}
        receipt = json.loads((runner.work/'generation-complete.json').read_text())
        assert receipt == {'identity':runner.identity,'result_hash':store.digest(result)}
        assert runner.replay('root', runner.ids) == result
    except (OSError, ValueError, KeyError, AssertionError):
        raise ValueError('生成安排批次或交界核對未全部完成；不能採用部分成果。') from None


def require_fresh(job):
    source = groups.planning_source(store.project(job['project_id']), job['target_id'])
    if not groups.plan_matches(source, job['input']['group_plan_hash'], job):
        raise ValueError('分鏡或生成用途已更新；請建立新安排，舊進度保留。')


def progress(job):
    if not job['input'].get('generation_pipeline'):
        return None
    try:
        return json.loads((store.DATA/'jobs'/job['id']/'generation-progress.json').read_text())
    except (OSError, ValueError):
        return {'kind':'generation_stages','label':'正在核對模型容量','completed':0,'total':None}


def receipts(job):
    if not job['input'].get('generation_pipeline'):
        return []
    rows = []
    work = store.DATA/'jobs'/job['id']
    try:
        full = json.loads((work/'context-budget.json').read_text()).get('input_tokens')
    except (OSError, ValueError):
        full = None
    for path in sorted(work.glob('*-attempt-*/context-budget.json')):
        try:
            value = json.loads(path.read_text())
            rows.append({'attempt':path.parent.name,'mode':'自適應生成安排','full_input_tokens':full,**value})
        except (OSError, ValueError):
            continue
    return rows
