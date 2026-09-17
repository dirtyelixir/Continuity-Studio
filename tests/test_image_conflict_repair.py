"""Bounded semantic correction with durable evidence and unchanged render gates."""
import copy
import json
from pathlib import Path
import pytest
from PIL import Image
from studio import image_prompts as ip, providers, store


@pytest.fixture
def case(tmp_path):
    image = tmp_path/'reference.png'
    Image.new('RGB', (16, 16), 'white').save(image)
    work = tmp_path/'job'/'preparation'
    basis = {'target_id': 'person', 'target_kind': 'character', 'high_reference_fidelity': False,
             'reference_policy': 'Preserve selected identity.',
             'requested_revision': 'Enlarge to head-and-shoulders; it still extends below the hips.'}
    provider = {'id': 'selected', 'kind': 'http', 'model': 'same-model'}
    result = {'target_id': 'person', 'visual_style': 'Neutral studio photography.',
              'appearance': 'A person in a white dress.', 'composition': 'Front head-and-shoulders portrait.',
              'lighting': 'Soft light.', 'requested_changes': 'Enlarge the portrait.',
              'omitted_context': [], 'conflicts': ['Head-and-shoulders versus below hips.']}
    args = [provider, basis, 'Head-and-shoulders portrait.', ['Image 1: identity'],
            'Original request: '+basis['requested_revision'], work]
    return args, [image], result


def invoke(case):
    args, images, _ = case
    return ip.prepare(*args, images=images)


def test_false_conflict_fixed_same_provider_pixels_original_preserved_and_reused(case, monkeypatch):
    args, images, original = case
    seen = []
    def run(provider, cap, prompt, refs, work):
        seen.append((provider, cap, prompt, refs))
        assert provider == args[0] and cap == 'image_prepare'
        assert [p.read_bytes() for p in refs] == [p.read_bytes() for p in images]
        result = copy.deepcopy(original)
        if len(seen) == 2:
            assert args[4] in prompt and store.encode(original) in prompt
            assert args[2] in prompt and args[3][0] in prompt
            result.update(conflicts=[], omitted_context=['Below hips describes the current defect.'])
        return result
    monkeypatch.setattr(providers, 'run', run)
    result, prompt = invoke(case)
    assert not result['conflicts'] and 'Enlarge the portrait.' in prompt
    assert len(seen) == 2
    assert json.loads((args[-1]/'result.json').read_text()) == original
    assert invoke(case) == (result, prompt) and len(seen) == 2
    assert json.loads((args[-1].with_name('preparation-correction')/'decision.json').read_text())['state'] == 'accepted'


def test_genuine_conflict_stops_after_one_review_including_recovery(case, monkeypatch):
    calls = []
    monkeypatch.setattr(providers, 'run', lambda *a: calls.append(a) or copy.deepcopy(case[2]))
    for _ in range(2):
        with pytest.raises(ip.ConflictError, match='已自動覆核'):
            invoke(case)
    assert len(calls) == 2
    assert not (case[0][-1]/'render-prompt.txt').exists()


@pytest.mark.parametrize('failure', ['schema', 'target', 'reference', 'empty', 'transport'])
def test_unrelated_failure_never_gets_semantic_retry(case, monkeypatch, failure):
    calls = []
    def run(*a):
        calls.append(a)
        result = copy.deepcopy(case[2])
        # Even mixed invalid fields plus conflicts must not take the semantic path.
        if failure == 'schema':result['extra'] = 'invalid'
        if failure == 'target':result['target_id'] = 'wrong'
        if failure == 'reference':result['appearance'] = 'Use Image 99.'
        if failure == 'empty':result['lighting'] = ''
        if failure == 'transport':raise RuntimeError('transport failure')
        return result
    monkeypatch.setattr(providers, 'run', run)
    with pytest.raises((ValueError, RuntimeError)):
        invoke(case)
    assert len(calls) == 1
    assert not case[0][-1].with_name('preparation-correction').exists()


@pytest.mark.parametrize('stage', ['before', 'initial', 'correction', 'reuse'])
def test_cancellation_prevents_consumption_and_extra_calls(case, monkeypatch, stage):
    args, _, original = case
    marker = args[-1].parent/'cancel-requested'
    marker.parent.mkdir(parents=True)
    calls = []
    if stage == 'before':marker.touch()
    def run(*a):
        calls.append(a)
        result = copy.deepcopy(original)
        if len(calls) == 2:result['conflicts'] = []
        if stage == 'initial' or stage == 'correction' and len(calls) == 2:marker.touch()
        return result
    monkeypatch.setattr(providers, 'run', run)
    if stage == 'reuse':
        invoke(case)
        marker.touch()
    with pytest.raises(RuntimeError, match='取消'):
        invoke(case)
    assert len(calls) == {'before':0, 'initial':1, 'correction':2, 'reuse':2}[stage]


def test_incomplete_correction_is_never_resubmitted_or_consumed(case, monkeypatch):
    calls = []
    def run(provider, cap, prompt, refs, work):
        calls.append(cap)
        if len(calls) == 1:return copy.deepcopy(case[2])
        # Raw output alone cannot prove a successful provider completion.
        result = copy.deepcopy(case[2]);result['conflicts'] = []
        (work/'result.json').write_text(store.encode(result))
        raise RuntimeError('transport incomplete')
    monkeypatch.setattr(providers, 'run', run)
    with pytest.raises(RuntimeError):invoke(case)
    with pytest.raises(ValueError, match='沒有完整結果'):invoke(case)
    assert len(calls) == 2


@pytest.mark.parametrize('change', ['provider', 'candidate', 'task', 'roles', 'pixels', 'result'])
def test_changed_evidence_cannot_consume_or_respend_correction(case, monkeypatch, change):
    calls = []
    def run(*a):
        calls.append(a)
        result = copy.deepcopy(case[2])
        if len(calls) == 2:result['conflicts'] = []
        return result
    monkeypatch.setattr(providers, 'run', run)
    invoke(case)
    args, images, original = case
    if change == 'provider':args[0]['model'] = 'other'
    if change == 'task':args[2] = 'Different task'
    if change == 'roles':args[3][0] = 'Image 1: style'
    if change == 'pixels':Image.new('RGB', (16, 16), 'black').save(images[0])
    if change == 'candidate':
        altered = copy.deepcopy(original);altered['conflicts'] = ['Other conflict']
        (args[-1]/'result.json').write_text(store.encode(altered))
    if change == 'result':
        p = args[-1].with_name('preparation-correction')/'result.json'
        r = json.loads(p.read_text());r['appearance'] = 'Tampered person';p.write_text(store.encode(r))
    with pytest.raises(ValueError):invoke(case)
    assert len(calls) == 2


def test_valid_first_candidate_needs_one_call(case, monkeypatch):
    calls = []
    result = copy.deepcopy(case[2]);result['conflicts'] = []
    monkeypatch.setattr(providers, 'run', lambda *a: calls.append(a) or result)
    assert invoke(case)[0] == ip.validate(result, case[0][1])
    assert len(calls) == 1


@pytest.mark.parametrize('failure', ['target', 'schema', 'reference', 'length'])
def test_corrected_candidate_still_passes_all_normal_gates(case, monkeypatch, failure):
    calls = []
    def run(*a):
        calls.append(a)
        result = copy.deepcopy(case[2])
        if len(calls) == 2:
            result['conflicts'] = []
            if failure == 'target':result['target_id'] = 'wrong'
            if failure == 'schema':result['extra'] = True
            if failure == 'reference':result['appearance'] = 'Use Image 99.'
            if failure == 'length':
                result['appearance'] = 'Long appearance. ' * 180
                result['composition'] = 'Long composition. ' * 180
                result['requested_changes'] = 'Long changes. ' * 180
        return result
    monkeypatch.setattr(providers, 'run', run)
    for _ in range(2):
        with pytest.raises(ValueError):invoke(case)
    assert len(calls) == 2
    assert not (case[0][-1]/'render-prompt.txt').exists()
