"""Separate source interpretation from the exact, single-image rendering brief.

Canonical dependency hashes deliberately remain in continuity.context; changing
prompt policy must not invalidate existing approved pixels or rewrite history.
"""
import copy
import hashlib
import json
import re
from . import asset_roles, store, models, production_methods, frame_moments, prompt_writing

VERSION = 'single-image-brief-v7'
REFERENCE_POLICY = production_methods.reference('reference-authority.md')
PLANNING = production_methods.reference('planning.md')

RULES = production_methods.reference('image-preparation.md')
REVISION_READING_RULES = (
    'Distinguish observations of current image defects from requirements for the desired output. '
    'For example, "Enlarge to head-and-shoulders; it still extends below the hips" requests a tighter crop; '
    'the latter clause describes the current defect. Read the complete revision and reference pixels in context. '
    'Preserve all explicit desired requirements and report genuinely irreconcilable requirements. '
    'Do not reinterpret an explicit new-output requirement as a defect observation merely to avoid a conflict.'
)


def split_feedback(feedback):
    pattern = r'\[High reference preservation\][\s\S]*?\[/High reference preservation\]'
    high = bool(re.search(pattern, feedback))
    return re.sub(pattern, '', feedback).strip(), high


def source(plan, target_id, feedback=''):
    from .continuity import find_target
    kind, target, shot = find_target(plan, target_id)
    feedback, high = split_feedback(feedback)
    data = {'policy': VERSION, 'target_id': target_id,
            'target_kind': target['kind'] if kind == 'entity' else 'frame',
            'legacy_style_context': plan['style'],
            'target': asset_roles.visual_identity(target) if kind == 'entity' else copy.deepcopy(target),
            'requested_revision': feedback, 'high_reference_fidelity': high,
            'render_contract': production_methods.render_contract(target['kind'] if kind == 'entity' else 'frame')}
    if shot:
        scene = next(s for s in plan['scenes'] if s['id'] == shot['scene_id'])
        ids = set(shot['entity_ids']) | {scene['location_id']}
        data['visual_context'] = {
            'scene': {k: scene[k] for k in ('location_id', 'time_of_day')},
            'framing': shot['framing'], 'angle': shot['angle'],
            'blocking': shot['blocking'],
            'moment_state': copy.deepcopy(target['state'] if target['moment']=='key' else shot[target['moment'] + '_state']),
            'canon': [asset_roles.visual_identity(e) for e in plan['canon'] if e['id'] in ids and asset_roles.is_visual(e)]}
        if target['moment']=='key':
            data['visual_context']['source_time']=target['source_time']
            data['visual_context']['composition_authority']='Target description controls this intermediate still; Shot framing/blocking describe the source opening and may have changed through the adopted camera/action.'
        if shot.get('direction') and scene.get('director_plan'):
            data['director_boundary']={'shot_purpose':shot['shot_purpose'],
                'visual_carrier':shot['direction']['visual_carrier'],
                'readability':shot['direction']['readability'],
                'reveal_constraints':[b['intent']['reveal_strategy'] for b in scene['director_plan']['beats'] if b['id'] in shot['direction']['beat_ids']],
                'moment_rule':'Freeze only the specified instant and supplied moment_state. Do not substitute the opening, ending or later result.'}
        data['frame_moment_contract'] = frame_moments.build(plan, target_id)
    else:
        data['location_times_context'] = list(dict.fromkeys(s['time_of_day'] for s in plan['scenes'] if s['location_id'] == target_id))
    return data


MOMENT_RECONCILIATION = (
    'FROZEN-MOMENT SINGLE AUTHORITY: the source carries a frame_moment_contract naming the exact source time and the '
    'authoritative structured state at that instant (state_source). That state owns DYNAMIC facts: pose, eyeline, '
    'hand/object possession, power, damage and reveal. The keyframe description owns composition (camera, framing, '
    'screen layout) and may supplement facts the state leaves unspecified. Reconcile stale descriptive dynamic detail '
    'in your prepared brief to the authoritative state: when a brief field would contradict the state at the source '
    'time, keep the state value and record the reconciliation in omitted_context as the original conflicting phrase '
    'plus the applied state (quote the phrase, then the state). Do not mutate the source, do not infer semantics '
    'from keyword matching, and do not override an explicit requested revision or a genuine contradiction inside the '
    'authoritative state or timeline. This explicit contract resolves the general legacy instruction that description and state both govern: they govern different scopes. Reserve the conflicts list for truly authoritative conflicts that the state '
    'itself cannot resolve; reconciled stale prose is not a conflict.'
)


OFF_STATE_KEYS = ('power', 'illumination')

OFF_STATE_INSTRUCTION = ('OFF-STATE RENDERING (affirmative instruction): the frozen moment declares an '
                         'inactive object in the state list above.')


def instruction(basis, task, roles):
    parts = [RULES, 'REVISION INTERPRETATION:\n' + REVISION_READING_RULES,
             'REFERENCE AUTHORITY:\n' + basis.get('reference_policy', ''),
             'TARGET FORMAT:\n' + task, 'ATTACHMENT ROLES:\n' + '\n'.join(roles)]
    # The shared writing principles arrive through the method bundle's routes; this adds the
    # contract for the specific task this target is, which the bundle cannot know on its own.
    contract = prompt_writing.contract_line(writing_task(basis))
    if contract:
        parts.insert(1, 'TASK CONTRACT:\n' + contract)
    if basis.get('frame_moment_contract'):
        parts.append('FROZEN-MOMENT RECONCILIATION:\n' + MOMENT_RECONCILIATION)
    parts.append('SOURCE FOR INTERPRETATION ONLY:\n' + store.encode(basis))
    return '\n'.join(parts)


class ConflictError(ValueError):
    """Only reported conflicts (not schema/transport/other validation faults).

    A nonempty conflict list is the single retryable preparation fault: the
    provider may have misread a current-image defect observation as a new
    requirement. Every other validation failure means the candidate is
    unusable and must not be re-evaluated.
    """


def writing_task(basis):
    """Which writing task this image is, for the shared task contract and checks."""
    operation = (basis.get('local_operation') or {}).get('operation')
    target = basis.get('target') or {}
    moment = target.get('moment') if isinstance(target, dict) else None
    return prompt_writing.task_for_image(basis.get('target_kind'), moment, operation)


def declared_states(basis):
    """Declared 'Off' state values for this target, in the words the brief will have to honour."""
    contract = basis.get('frame_moment_contract') or {}
    values = []
    for state in contract.get('states') or []:
        key = str(state.get('key', '')).strip().lower()
        value = str(state.get('value', '')).strip()
        if key in OFF_STATE_KEYS and value.lower().startswith('off'):
            values.append(value)
    return values


def writing_findings(result, basis, reference_count=None):
    """Deterministic review of a written brief. Mechanical faults only; never creative judgement."""
    fields = {key: result[key] for key in
              ('visual_style', 'appearance', 'composition', 'lighting', 'requested_changes')
              if isinstance(result.get(key), str)}
    return prompt_writing.check(fields, writing_task(basis), reference_count=reference_count,
                               declared_states=declared_states(basis))


def validate(result, basis):
    result = models.PreparedImage.model_validate(result).model_dump()
    if result['target_id'] != basis['target_id']:
        raise ValueError('圖片提示詞整理結果屬於其他目標。')
    fields = ('visual_style', 'appearance', 'composition', 'lighting', 'requested_changes')
    for key in fields:
        text = result[key]
        if key != 'requested_changes' and not text.strip():
            raise ValueError('圖片提示詞缺少可執行的視覺內容：' + key)
        if re.search(r'<(?:Entity|Subject|Picture|Video|Audio)\b|\b(?:Image|Picture)\s+\d|\[High reference preservation\]|Canonical production context|subject_definitions:|overall_soundscape:|non_diegetic_music:', text, re.I):
            raise ValueError('圖片提示詞混入參考編號、來源模板或影音段落：' + key)
    if result['conflicts']:
        raise ConflictError('圖片設定存在需要修訂的衝突：' + '；'.join(result['conflicts']))
    findings, blocking = writing_findings(result, basis)
    if blocking:
        # A mechanically provable writing fault: the same single repair retry as a conflict,
        # because the writer can fix it without any decision the model is not allowed to make.
        raise ConflictError('提示詞有可機械判定的寫作錯誤：' + prompt_writing.finding_text(blocking))
    return result


def fidelity(kind):
    detail = {
        'location': 'Preserve the referenced architecture, connected layout, openings, railings, materials and colors shared across its parts. Preserve fixed markings exactly as specified for THIS target; treat the reference as a different floor or sub-area where the explicit frame location differs, and do not import another floor’s unique marks or signage.',
        'prop': 'Preserve the referenced object silhouette, proportions, materials, colors and distinctive details.',
        'character': 'Preserve the same face, age, hair, clothing, body proportions and asymmetric details across the required views.',
        'crowd': 'Preserve multiple distinct people and their individual appearance and wardrobe; avoid cloned faces.',
        'frame': 'Preserve the referenced visible identities, objects and architecture in the specified frozen composition.'
    }[kind]
    return 'High reference preservation: ' + detail + ' Make only the requested changes. Respect each assigned reference role.'


def off_state_note(basis):
    """Affirmative restatement of a declared switched-off prop, or '' when none is declared.

    Measured on this pipeline: the same brief over the same pixels rendered a glowing bulb while
    the prompt said 'unlit ... no filament glow'. Negation inside a positive prompt can summon the
    concept, and this pipeline has no negative prompt to fall back on (the klein graph zeroes the
    negative conditioning and runs cfg 1.0), so the declared state is restated as what IS present
    instead of what is absent. Only an exact 'Off' power/illumination declaration triggers it, so
    unrelated prompts stay byte-identical.
    """
    contract = basis.get('frame_moment_contract') or {}
    names = contract.get('identity_names') or {}
    notes = []
    for state in contract.get('states') or []:
        key = str(state.get('key', '')).strip().lower()
        value = str(state.get('value', '')).strip()
        if key not in OFF_STATE_KEYS or not value.lower().startswith('off'):
            continue
        entity = str(state.get('entity_id', ''))
        notes.append(f'{names.get(entity, entity)} ({entity}).{key} = "{value}"')
    if not notes:
        return ''
    return (OFF_STATE_INSTRUCTION + ' Declared: ' + '; '.join(notes) + '. Render each of those objects '
            'in its declared state: switched off, its light-emitting parts reading as cold, dark and '
            'still material, so a viewer reads an inactive object. All light in the frame comes from '
            'the sources named in Lighting above.')


def compile_prompt(result, basis, task, roles):
    result = validate(result, basis)
    sections = [task, 'Visual style: ' + result['visual_style'].strip(),
                'Appearance: ' + result['appearance'].strip(),
                'Composition: ' + result['composition'].strip(),
                'Lighting: ' + result['lighting'].strip()]
    note = off_state_note(basis)
    if note:
        sections.append(note)
    if result['requested_changes'].strip():
        sections.append('Requested changes: ' + result['requested_changes'].strip())
    if roles:
        sections.append('Reference images:\n' + '\n'.join(roles))
    if basis.get('primary_design_input'):
        sections.append('Design priority: the selected PRIMARY SUBJECT/DESIGN INPUT defines this candidate. Preserve its visible design; do not restore the old appearance or mix identities. Apply only the requested changes and required output layout.')
    if basis['high_reference_fidelity']:
        sections.append(fidelity(basis['target_kind']))
    if basis['target_kind'] != 'character':
        sections.append('No watermarks, unsolicited captions, added text labels or montage. Preserve expressly required in-scene lettering and signage exactly as described for this target.')
    contract = basis.get('render_contract')
    if contract:
        if contract['target_kind'] != basis['target_kind'] or not contract['rules']:
            raise ValueError('圖片製作規格與目標不符；未開始生成。')
        sections.append('Required production constraints:\n' + '\n'.join(contract['rules']))
    text = '\n\n'.join(sections)
    if len(text) > 7500:
        raise ValueError('圖片提示詞超出 7500 字元；請收窄要求，未開始生圖。')
    # Last assembly point before the renderer: the text that actually ships is checked here, so a
    # fault cannot be introduced after preparation and still reach the renderer.
    _, blocking = prompt_writing.check({'render_prompt': text}, writing_task(basis),
                                       reference_count=len(roles or []),
                                       declared_states=declared_states(basis))
    if blocking:
        raise ValueError('最終圖片提示詞有可機械判定的寫作錯誤：' + prompt_writing.finding_text(blocking))
    return text


def freeze_references(images, work):
    """Snapshot actual pixels once for both vision preparation and rendering."""
    import hashlib, json, shutil
    from pathlib import Path
    work.mkdir(parents=True, exist_ok=True)
    manifest=[]; frozen=[]
    for index, source in enumerate(images, 1):
        source=Path(source).resolve()
        target=(work/f'reference-{index}{source.suffix.lower()}').resolve()
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                raise ValueError('參考圖與已保存的工作輸入不同；請建立新工作。')
        else:
            shutil.copyfile(source,target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('參考圖複製驗證失敗；未開始生成。')
        frozen.append(target)
        manifest.append({'image_number':index,'source':str(source),'path':str(target),'sha256':digest})
    path=work/'reference-inputs.json'
    encoded=json.dumps(manifest,ensure_ascii=False,indent=2)
    if path.exists() and path.read_text()!=encoded:
        raise ValueError('參考圖清單與已保存的工作輸入不同；請建立新工作。')
    path.write_text(encoded)
    return frozen, manifest


def preparation_fingerprint(inp, images):
    """Provider-independent identity of the complete creative request and pixels."""
    return store.digest({'source': inp['image_source'], 'task': inp['image_task'],
                         'roles': inp['image_reference_roles'], 'prompt': inp['prompt'],
                         'method': inp.get('production_method'),
                         **({'local_lora_context': inp['image_lora_context']} if inp.get('image_lora_context') else {}),
                         'reference_board': inp.get('provider_config', {}).get('kind') == 'codex' and len(images)>5,
                         'images': [hashlib.sha256(p.read_bytes()).hexdigest() for p in images]})


def reusable_preparation(job, fingerprint):
    """Reuse a frozen brief, never invoke an old provider or re-submit old media work."""
    for previous in store.jobs(job['project_id']):
        if (previous['id'] == job['id'] or previous['capability'] != 'image'
                or previous['target_id'] != job['target_id']
                or previous['state'] not in ('succeeded', 'failed', 'interrupted')):
            continue
        inp = previous['input']
        if (inp.get('image_preparation_fingerprint') != fingerprint
                or not inp.get('image_preparation') or not inp.get('render_prompt_hash')):
            result = saved_lora_failure(previous, fingerprint)
            if result is not None:
                return result, {'mode': 'reused', 'job_id': previous['id'],
                                'original_job_id': previous['id'],
                                'provider': inp['image_preparer_config']['id'],
                                'stage': 'saved-before-lora-validation'}
            continue
        if store.digest(inp.get('image_prompt', '')) != inp['render_prompt_hash']:
            continue
        # Validate both the source association and the exact saved compiler output.
        result = validate(inp['image_preparation'], job['input']['image_source'])
        compiled = compile_prompt(result, inp['image_source'], inp['image_task'], inp['image_reference_roles'])
        if inp['provider_config']['kind']=='codex' and len(inp['images'])>5:
            from .reference_boards import transport_note
            compiled += '\n\nReference transport: ' + transport_note(len(inp['images']))
        if compiled != inp['image_prompt']:
            continue
        origin = inp.get('image_preparation_origin') or {}
        return result, {'mode': 'reused', 'job_id': previous['id'],
                        'original_job_id': origin.get('original_job_id', previous['id']),
                        'provider': origin.get('provider', inp.get('image_preparer_config', {}).get('id'))}
    return None, None


def saved_lora_failure(previous, fingerprint):
    """Read an intact pre-render checkpoint on an explicit, identical retry."""
    from . import image_loras
    from pathlib import Path
    work = store.DATA/'jobs'/previous['id']
    if (previous['state'] != 'failed' or previous.get('error') != image_loras.EVIDENCE_ERROR
            or (work/'comfy-receipt.json').exists() or (work/'cancel-requested').exists()):
        return None
    inp = previous['input']
    preparation = work/'preparation'
    try:
        if ((preparation/'source.json').read_text() != store.encode(inp['image_source'])
                or (preparation/'request.txt').read_text() != inp['prompt']):
            return None
        manifest = json.loads((preparation/'inputs/reference-inputs.json').read_text())
        if len(manifest) != len(inp['images']):
            return None
        images = []
        for index, entry in enumerate(manifest, 1):
            path = Path(entry['path'])
            if (entry['image_number'] != index or path.resolve().parent != (preparation/'inputs').resolve()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']):
                return None
            images.append(path)
        if preparation_fingerprint(inp, images) != fingerprint:
            return None
        result = validate(json.loads((preparation/'result.json').read_text()), inp['image_source'])
        compiled = compile_prompt(result, inp['image_source'], inp['image_task'], inp['image_reference_roles'])
        if compiled != (preparation/'render-prompt.txt').read_text():
            return None
        selection, _ = image_loras.grounded_selection(result.get('local_lora_selection'), inp['image_lora_context'], result)
        image_loras.apply(inp['local_image_plan'], selection, inp['image_lora_context'], result)
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None

def _check_cancel(work):
    if any((p/'cancel-requested').is_file() for p in (work, work.parent)):
        raise RuntimeError('使用者已取消工作。')


def _repair_conflict(provider, basis, task, roles, request, work, frozen, original, error):
    """One durable same-provider interpretation review; never resubmit an attempt."""
    from . import providers
    correction = work.with_name(work.name + '-correction')
    _check_cancel(work)
    _check_cancel(correction)
    identity = store.digest({'policy': VERSION, 'provider': provider, 'basis': basis,
                             'task': task, 'roles': roles, 'request': request,
                             'candidate': original,
                             'pixels': [hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen]})
    marker = correction/'attempt.json'
    output = correction/'result.json'
    decision = correction/'decision.json'
    if correction.exists():
        if not marker.is_file() or json.loads(marker.read_text()).get('identity') != identity:
            raise ValueError('圖片自動覆核記錄與本次要求不符；請建立新工作，原記錄保留。')
        status = json.loads(decision.read_text()) if decision.is_file() else {}
        if not output.is_file() or not status.get('result_hash'):
            raise ValueError('圖片提示詞已嘗試自動覆核一次，但沒有完整結果；原記錄已保留，未再次提交。')
        candidate = json.loads(output.read_text())
        if store.digest(candidate) != status['result_hash']:
            raise ValueError('圖片自動覆核結果與保存記錄不符；未開始生成。')
    else:
        correction.mkdir()
        repair_request = (request + '\n\nONE BOUNDED CONFLICT RE-EVALUATION:\n' + REVISION_READING_RULES
                          + '\nRe-evaluate the following previous candidate against the original request above and the SAME attached pixels. '
                          'Keep the original target, reference authority, format, all explicit requested changes and fixed details. '
                          'Never drop a desired requirement or clear conflicts just to pass validation. '
                          'If the conflict was a misreading, return a corrected full result and explain the misreading in omitted_context, '
                          'quoting the relevant source phrase. If requirements truly conflict, retain them in conflicts. '
                          'Return the original image-preparation JSON schema only.\n'
                          'TARGET FORMAT:\n' + task + '\nATTACHMENT ROLES:\n' + '\n'.join(roles)
                          + '\nORIGINAL SOURCE:\n' + store.encode(basis)
                          + '\nPREVIOUS CANDIDATE (evidence, not authority):\n' + store.encode(original)
                          + '\nVALIDATION ERROR:\n' + str(error))
        (correction/'source.json').write_text(store.encode(basis))
        (correction/'request.txt').write_text(repair_request)
        (correction/'original-result.json').write_text(store.encode(original))
        # Written before the provider call: incomplete attempts cannot spend again.
        marker.write_text(store.encode({'identity': identity, 'provider': provider['id'], 'attempts': 1}))
        decision.write_text(store.encode({'state': 'attempted'}))
        try:
            _check_cancel(work)
            _check_cancel(correction)
            candidate = providers.run(provider, 'image_prepare', repair_request, frozen, correction)
            output.write_text(store.encode(candidate))
            _check_cancel(work)
            _check_cancel(correction)
        except Exception:
            decision.write_text(store.encode({'state': 'incomplete'}))
            raise
        decision.write_text(store.encode({'state': 'received', 'result_hash': store.digest(candidate)}))
    _check_cancel(work)
    _check_cancel(correction)
    try:
        result = validate(candidate, basis)
        prompt = compile_prompt(result, basis, task, roles)
    except Exception as exc:
        decision.write_text(store.encode({'state': 'rejected', 'result_hash': store.digest(candidate), 'error': str(exc)}))
        if isinstance(exc, ConflictError):
            frame_moments.write(work, candidate, basis)
            # Surface the actual reason: a mechanical writing fault carries its own precise message,
            # and reporting an empty conflict list here would hide why the candidate was rejected.
            reason = str(exc) or ('；'.join(candidate.get('conflicts') or []) or '原因不明')
            raise ConflictError('已自動覆核提示詞一次，仍未解決：' + reason) from exc
        raise
    decision.write_text(store.encode({'state': 'accepted', 'result_hash': store.digest(candidate)}))
    return result, prompt


def prepare(provider, basis, task, roles, request, work, images=()):
    """Prepare a brief, with one source-preserving review of reported conflicts."""
    from . import providers
    _check_cancel(work)
    if basis.get('reference_policy') and len(images)!=len(roles):
        raise ValueError('參考圖與用途清單不一致；未開始生成。')
    work.mkdir(parents=True, exist_ok=True)
    frozen, manifest = freeze_references(images, work/'inputs')
    saved = work/'result.json'
    if saved.is_file():
        if ((work/'source.json').read_text()!=store.encode(basis)
                or (work/'request.txt').read_text()!=request):
            raise ValueError('已保存的圖片整理結果來自不同要求；請建立新工作，原結果保留。')
        result = json.loads(saved.read_text())
    else:
        (work/'source.json').write_text(store.encode(basis))
        (work/'request.txt').write_text(request)
        _check_cancel(work)
        result = providers.run(provider, 'image_prepare', request, frozen, work)
        saved.write_text(store.encode(result))
    _check_cancel(work)
    try:
        result = validate(result, basis)
    except ConflictError as error:
        result, prompt = _repair_conflict(provider, basis, task, roles, request, work, frozen, result, error)
        frame_moments.write(work, result, basis)
    else:
        prompt = compile_prompt(result, basis, task, roles)
        frame_moments.write(work, result, basis)
    _check_cancel(work)
    (work/'render-prompt.txt').write_text(prompt)
    return result, prompt
