import copy
import io
import zipfile
import pytest
from studio import delivery, h3, speech_direction, store
from test_production import client, plan
from test_delivery import established, edit_payload


def test_spoken_and_silent_prompts_keep_canonical_timing_and_nonverbal_actions(plan):
    shot = plan['shots'][0]
    for text in [delivery.chapter_draft(plan, shot, []), h3.compile_shot(plan, shot, [])['text']]:
        assert text.count('<d>[English] Light.</d>') == 1
        assert 'synchronize natural mouth articulation' in text
        d = shot['dialogue'][0]
        assert f'Ada {d["start"]:.2f}–{d["end"]:.2f}s' in text
        speech_direction.validate_dialogue(text, shot)
    shot['dialogue'] = []
    shot['soundscape'] = 'A small intake of breath, then a switch click.'
    text = delivery.chapter_draft(plan, shot, [])
    assert 'no character speaks' in text and 'No speech-like mouth movements' in text
    assert shot['soundscape'] in text and 'except for explicitly described nonverbal actions' in text
    assert '<d>' not in text


def test_validation_rejects_extra_duplicate_untagged_and_reordered_dialogue(plan):
    shot = plan['shots'][0]
    text = delivery.chapter_draft(plan, shot, [])
    for bad in [text + '<d>[English] Hello.</d>', text + '<d>[English] Light.</d>',
                text.replace('<d>[English] Light.</d>', 'Light.')]:
        with pytest.raises(ValueError, match='canonical dialogue'):
            speech_direction.validate_dialogue(bad, shot)
    second = {**shot['dialogue'][0], 'text': 'Stay here.'}
    shot['dialogue'].append(second)
    with pytest.raises(ValueError):
        speech_direction.validate_dialogue('<d>[English] Stay here.</d><d>[English] Light.</d>', shot)
    shot['dialogue'] = []
    with pytest.raises(ValueError):
        speech_direction.validate_dialogue('<d>[English] Hello.</d>', shot)


def test_old_saved_direction_gets_guard_in_page_and_export_without_mutation(client, plan):
    plan['shots'][0]['dialogue'] = []
    pid = established(client, plan)
    state = client.get('/api/projects/' + pid).json()
    chapter = state['delivery']['scenes'][0]['chapters'][0]
    old = '\n'.join(l for l in chapter['shot_prompt'].splitlines()
                    if not l.startswith(speech_direction.PREFIX))
    payload = edit_payload(client, pid)
    payload['scenes'] = {'scene': {'chapters': {'shot': {'shot_prompt': old}}}}
    assert client.put('/api/projects/' + pid + '/delivery', json=payload).status_code == 200
    before = copy.deepcopy(store.project(pid))
    updated = client.get('/api/projects/' + pid).json()['delivery']['scenes'][0]['chapters'][0]
    assert 'no character speaks' in updated['shot_prompt'] and not updated['issues']
    assert updated['shot_prompt'].count(speech_direction.PREFIX) == 1
    assert store.setting('delivery:' + pid)['scenes']['scene']['chapters']['shot']['shot_prompt'] == old
    assert store.project(pid) == before and not store.jobs(pid)
    archive = zipfile.ZipFile(io.BytesIO(client.get('/api/projects/' + pid + '/export').content))
    assert archive.read('ref2/scenes/scene/chapters/shot/shot.txt').decode() == updated['shot_prompt']


def test_guard_is_idempotent_and_does_not_invent_visible_offscreen_speaker(plan):
    shot = plan['shots'][0]
    shot['dialogue'][0]['delivery'] = 'Off-screen, softly.'
    text = delivery.chapter_draft(plan, shot, [])
    assert speech_direction.apply(text, plan, shot) == text
    assert 'Off-screen, softly.' in text and 'Whenever the speaker is visible' in text
