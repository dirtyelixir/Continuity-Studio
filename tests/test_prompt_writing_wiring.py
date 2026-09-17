"""End-to-end wiring: the shared writing rules must reach the prompt a real Studio job actually sends.

Unit tests that call the new helpers directly prove nothing about wiring. These tests drive the
FastAPI application the same way the UI does — create a project, POST a job, execute it — and
inspect the exact text the model provider and the renderer receive, on every path a user can take:
initial generation, a revision with feedback, the bounded conflict repair, and the final assembly
guard that stops a mechanically-provable fault before the renderer is ever called.

The provider is a deterministic double: no generation is started and nothing is written outside the
temporary data root.
"""
import copy
import json
from pathlib import Path

import pytest
from PIL import Image

from studio import engine, image_prompts, models, prompt_writing, providers, store
from test_production import client, plan, create, add_asset  # noqa: F401  (fixtures used by name)

PRINCIPLES_MARK = 'Decide what the frame is for'


def approve_canon(client, plan, pid):
    """A frame cannot be rendered before its canonical references are approved — same as the UI."""
    add_asset(pid, plan, 'ada')
    add_asset(pid, plan, 'room')


def brief_for(target='start', **overrides):
    """A minimal valid preparation result; overrides let a test inject a specific fault."""
    data = {'target_id': target,
            'visual_style': 'Stop-motion, 16:9, restrained palette.',
            'appearance': 'Ada with a black bob and a mustard raincoat beside a wooden bench.',
            'composition': 'Eye-level medium shot, Ada screen left with her fingertips on the switch.',
            'lighting': 'Dim window light through the round rear window.',
            'requested_changes': '', 'omitted_context': [], 'conflicts': [],
            'local_lora_selection': {'summary': '無需額外 LoRA。', 'selected': []}}
    data.update(overrides)
    return data


def fake_render(work):
    """A structured, non-uniform fixture frame: the blank/noise guard must not be what fails."""
    from PIL import ImageDraw
    path = Path(work) / 'fixture.png'
    im = Image.new('RGB', (1376, 768), 'white')     # real render dimensions
    draw = ImageDraw.Draw(im)
    draw.rectangle([60, 60, 700, 700], fill='black')
    draw.rectangle([820, 160, 1300, 380], fill=(120, 90, 40))
    draw.ellipse([900, 440, 1180, 700], fill=(40, 70, 120))
    im.save(path)
    return path


def fake_result(capability, result_for, calls, work):
    """Deterministic provider double covering every stage a real image job runs."""
    if capability == 'image_prepare':
        n = len([c for c in calls if c['capability'] == 'image_prepare'])
        return copy.deepcopy(result_for(n))
    if capability == 'qc':
        return {'verdict': 'pass', 'summary': 'Consistent with the frozen moment.', 'issues': []}
    path = fake_render(work)
    return {'image_path': str(path), 'notes': 'Test fixture; not generation.'}


@pytest.fixture
def driver(client, plan, monkeypatch):
    """Drive real jobs, capturing every prompt handed to a provider and every renderer call."""
    from studio import comfy_images
    monkeypatch.setattr(comfy_images, 'preflight', lambda work: None)
    from studio import image_loras
    real_snapshot = image_loras.snapshot

    def no_lora_candidates(plan, info=None):
        context = real_snapshot(plan, info)      # keep the real family/model pairing
        context['candidates'] = []
        return context
    monkeypatch.setattr(image_loras, 'snapshot', no_lora_candidates)
    pid = create(client, plan)
    approve_canon(client, plan, pid)
    monkeypatch.setattr(engine.POOL, 'submit', lambda *a: None)
    store.put_setting('routing', {'image_review': 'manual'})
    calls = []

    def install(result_for):
        def run(provider, capability, prompt, images, work):
            calls.append({'capability': capability, 'prompt': prompt,
                          'provider': provider['id'], 'work': Path(work)})
            return fake_result(capability, result_for, calls, work)
        monkeypatch.setattr(providers, 'run', run)
    return pid, calls, install, client


def generate(client, pid, target='start', **kwargs):
    job = engine.enqueue(pid, models.JobRequest(capability='image', target_id=target,
                                                image_provider='comfy_local', force=True,
                                                **kwargs))['job']
    engine.execute(job['id'])
    return store.job(job['id'])


def prepare_calls(calls):
    return [c for c in calls if c['capability'] == 'image_prepare']


def test_initial_generation_prompt_carries_principles_and_task_contract(driver):
    pid, calls, install, client = driver
    install(lambda n: brief_for('start'))
    done = generate(client, pid)
    assert done['state'] == 'succeeded', done['error']

    sent = prepare_calls(calls)
    assert len(sent) == 1, 'one preparation attempt for a clean first pass'
    prompt = sent[0]['prompt']
    # The shared principles really are in what the model received…
    assert PRINCIPLES_MARK in prompt
    assert 'SHARED PROMPT-WRITING METHOD' in prompt or 'Prompt writing' in prompt
    # …and the task contract is the one this target actually is.
    basis_task = image_prompts.writing_task(done['input']['image_source'])
    assert basis_task == 'exact_start_keyframe', basis_task
    contract = prompt_writing.contract_line(basis_task)
    assert contract.split('.')[0] in prompt
    # The method bundle is recorded on the job, so the rules used are auditable per job.
    assert done['input']['production_method']['version']
    assert any('prompt-writing.md' in name
               for name in done['input']['production_method']['instruction_files']), \
        'the job receipt must record that the shared writing rules were used'


def test_revision_path_carries_the_same_rules(client, plan, monkeypatch):
    """A revision with feedback must not quietly fall back to an older instruction."""
    from studio import comfy_images
    monkeypatch.setattr(comfy_images, 'preflight', lambda work: None)
    from studio import image_loras
    real_snapshot = image_loras.snapshot

    def no_lora_candidates(plan, info=None):
        context = real_snapshot(plan, info)      # keep the real family/model pairing
        context['candidates'] = []
        return context
    monkeypatch.setattr(image_loras, 'snapshot', no_lora_candidates)
    pid = create(client, plan)
    approve_canon(client, plan, pid)
    monkeypatch.setattr(engine.POOL, 'submit', lambda *a: None)
    store.put_setting('routing', {'image_review': 'manual'})
    seen = []

    def run(provider, capability, prompt, images, work):
        seen.append({'capability': capability, 'prompt': prompt})
        return fake_result(capability, lambda n: brief_for(
            'start', requested_changes='Tighten to the toggle.'), seen, work)

    monkeypatch.setattr(providers, 'run', run)
    done = generate(client, pid, feedback='Tighten the framing onto the toggle.')
    assert done['state'] == 'succeeded', done['error']
    prompt = [c['prompt'] for c in seen if c['capability'] == 'image_prepare'][0]
    assert PRINCIPLES_MARK in prompt
    assert 'Tighten the framing onto the toggle.' in prompt
    render_prompt = (store.DATA / 'jobs' / done['id'] / 'preparation' / 'render-prompt.txt').read_text()
    assert 'Tighten to the toggle.' in render_prompt


def test_conflict_repair_path_keeps_the_same_rules(driver):
    """The bounded repair re-states the request, so the rules must still be present there."""
    pid, calls, install, client = driver

    def result_for(n):
        if n == 1:                      # first attempt claims an unreconcilable conflict
            return brief_for('start', conflicts=['The toggle is both hidden and required visible.'])
        return brief_for('start')

    install(result_for)
    done = generate(client, pid)
    assert done['state'] == 'succeeded', done['error']
    sent = prepare_calls(calls)
    assert len(sent) == 2, 'exactly one repair attempt'
    for call in sent:
        assert PRINCIPLES_MARK in call['prompt'], 'the repair request must carry the same rules'
    assert 'ONE BOUNDED CONFLICT RE-EVALUATION' in sent[1]['prompt']


def test_provable_writing_fault_never_reaches_the_renderer(driver):
    """A mechanically provable fault must stop at preparation, not ship to the renderer."""
    pid, calls, install, client = driver
    # Unsupported renderer syntax is mechanically provable, so it must never ship.
    bad = brief_for('start', composition='Ada at the bench, lantern weight (toggle:1.3) in frame.')
    install(lambda n: bad)
    done = generate(client, pid)
    assert done['state'] == 'failed'
    assert '寫作錯誤' in (done['error'] or '')
    # The renderer was never called with the faulty text.
    assert not [c for c in calls if c['capability'] == 'image'], \
        'the faulty prompt leaked past preparation to the renderer'


def test_resulting_render_prompt_is_the_checked_text(driver):
    """The text on disk for the renderer is exactly the text the checks approved."""
    pid, calls, install, client = driver
    install(lambda n: brief_for('start'))
    done = generate(client, pid)
    assert done['state'] == 'succeeded', done['error']
    on_disk = (store.DATA / 'jobs' / done['id'] / 'preparation' / 'render-prompt.txt').read_text()
    basis = done['input']['image_source']
    compiled = image_prompts.compile_prompt(json.loads(
        (store.DATA / 'jobs' / done['id'] / 'preparation' / 'result.json').read_text()), basis,
        done['input']['image_task'], done['input']['image_reference_roles'])
    assert on_disk == compiled
    _, hard = prompt_writing.check({'render_prompt': on_disk},
                                   image_prompts.writing_task(basis),
                                   reference_count=len(done['input']['image_reference_roles']))
    assert not hard, 'the shipped render prompt must pass the deterministic checks'
