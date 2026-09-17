"""Bounded, durable text verification before a frozen frame reaches rendering."""
import hashlib
import json
from . import models, providers, store

VERSION = 'frame-moment-preflight-v1'
PLANNING = """FROZEN-MOMENT SYNCHRONIZATION: For canonical Shots edit canonical_state moments/transitions for dynamic facts and canonical compositions for framing; keep timed beats/action/blocking/expression consistent. Studio recompiles start_state/end_state, frame.state and frame.description before adoption; those projections are not independently authored state. Do not remove canonical_state or revise semantic state only in prose. For legacy Shots, exact start_state/end_state and interior keyframe.state own explicitly stated dynamic facts; Studio migrates them before commit and logs superseded descriptive clauses. An explicit action change must update authoritative state and timing. Preserve canon, dialogue, unrelated scope and ordinary unknown details. Genuine authoritative state/timing conflicts must be rejected before formal adoption."""
REVIEW = '''FROZEN-MOMENT CONSISTENCY: Explicitly compare each affected keyframe description with its exact start_state/end_state or interior frame.state, and compare those states with timed action beats and reveal sequence. Report inconsistent derived prose or authoritative state/timing as concrete issues with literal evidence; do not pass a proposal whose descriptions and states disagree. Check this before media generation, independently of later pixel review.'''


def receipt(job):
    """Read-only public receipt, including failures before job input was updated."""
    path = store.DATA/'jobs'/job['id']/'moment-verification.json'
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return {k:v for k,v in value.items() if k not in ('prepared_image','render_prompt')}


def ensure(provider, basis, task, roles, request, result, prompt, images, work):
    """Verify the actual brief, repair once with the same preparer, never render."""
    from . import image_prompts
    if not basis.get('frame_moment_contract'):
        return result, prompt, None
    work.mkdir(parents=True, exist_ok=True)
    receipt = work/'moment-verification.json'
    identity = store.digest([VERSION, provider, basis, task, roles, request, result, prompt,
                             [hashlib.sha256(p.read_bytes()).hexdigest() for p in images]])

    def cancel():
        image_prompts._check_cancel(work)

    def save(value):
        receipt.write_text(store.encode({'version': VERSION, 'identity': identity, **value}))

    cancel()
    if receipt.is_file():
        old = json.loads(receipt.read_text())
        if old.get('identity') != identity:
            raise ValueError('畫面時刻檢查的來源或參考圖已改變；保留原記錄，請從最新來源建立工作。')
        if old.get('state') != 'accepted':
            raise ValueError('畫面時刻檢查已嘗試但未通過；未重複提交或開始生圖。' + old.get('error', ''))
        candidate = old['prepared_image']
        compiled = image_prompts.compile_prompt(candidate, basis, task, roles)
        if store.digest([candidate, compiled]) != old.get('output_hash') or compiled != old['render_prompt']:
            raise ValueError('保存的畫面時刻檢查結果不完整；未開始生圖。')
        return candidate, compiled, old

    # Write intent before any provider call. An incomplete attempt cannot silently spend again.
    save({'state': 'attempted'})
    base = ('''Check the ACTUAL prepared still-image rendering brief against the frozen moment source. Return ReviewResult JSON: verdict pass/revise/uncertain, summary, issues (specific actionable strings). This is a TEXT preflight; do not claim to inspect generated pixels. No tools or media.
Use frame_moment_contract and visual_context.moment_state as the authority for explicit dynamic facts at this exact source time. Check every applicable eyeline, pose, hand/prop ownership, power/illumination, damage and reveal state in the actual visual fields. Check composition and compatible unique details against the target description. A stale lower-priority descriptive clause is not an unresolved conflict when the brief already follows the authoritative state. Check that later beats have not leaked into this still; do not require depicting a tracked offscreen fact. Explicit requested revisions remain binding and cannot be silently discarded. A genuine contradiction among authoritative state/timing/request requirements must be reported. Do not reward copied state arrays or notes: judge what the renderer will actually be told, including contradictions across appearance/composition/lighting/requested_changes. State affirmative proof is unnecessary for non-visible facts. If information is inadequate return uncertain. Pass requires no issues. Do not critique aesthetic choices or unrelated identity/layout beyond this synchronization scope.
SOURCE (interpretation only):\n''' + store.encode(basis))

    def check(candidate, compiled, folder):
        cancel()
        folder.mkdir(parents=True, exist_ok=True)
        response = providers.run(provider, 'qc', base + '\nACTUAL PREPARED IMAGE:\n' + store.encode(candidate)
                                 + '\nACTUAL RENDER PROMPT:\n' + compiled, [], folder)
        response = models.ReviewResult.model_validate(response).model_dump()
        (folder/'result.json').write_text(store.encode(response))
        cancel()
        return response

    try:
        first = check(result, prompt, work/'moment-check')
        checks = [first]
        repaired = False
        if first['verdict'] != 'pass' or first['issues']:
            if first['verdict'] == 'uncertain' or not first['issues']:
                raise ValueError('生圖前未能確認畫面時刻一致：' + first['summary'])
            correction = (request + '\nONE AUTOMATIC FROZEN-MOMENT SYNCHRONIZATION REPAIR. '
                          'Return the complete image_prepare schema. Correct the actual brief using the source authority and the concrete findings below. '
                          'Preserve all compatible composition, visible identity, unique details, explicit requested changes and reference roles. '
                          'Do not rewrite source states, timing, canon or dialogue. Record each superseded descriptive phrase and its authoritative replacement in omitted_context. '
                          'Keep genuine authoritative conflicts in conflicts; never clear a conflict only to obtain pass. '
                          'No tools or media.\nPREVIOUS BRIEF:\n' + store.encode(result)
                          + '\nTEXT PREFLIGHT FINDINGS:\n' + store.encode(first))
            cancel()
            (work/'moment-repair').mkdir(parents=True, exist_ok=True)
            result = providers.run(provider, 'image_prepare', correction, images, work/'moment-repair')
            (work/'moment-repair'/'result.json').write_text(store.encode(result))
            cancel()
            result = image_prompts.validate(result, basis)
            prompt = image_prompts.compile_prompt(result, basis, task, roles)
            repaired = True
            second = check(result, prompt, work/'moment-recheck')
            checks.append(second)
            if second['verdict'] != 'pass' or second['issues']:
                raise ValueError('生圖前自動同步一次後仍有畫面時刻問題：' + second['summary']
                                 + '；'.join(second['issues']))
        value = {'state': 'accepted', 'repaired': repaired, 'checks': checks,
                 'prepared_image': result, 'render_prompt': prompt,
                 'output_hash': store.digest([result, prompt]),
                 'scope': 'provider text consistency check; not proof of rendered pixels'}
        cancel()
        save(value)
        return result, prompt, json.loads(receipt.read_text())
    except Exception as exc:
        save({'state': 'blocked', 'error': str(exc)})
        raise
