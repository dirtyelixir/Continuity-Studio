"""Explicit speech boundaries derived from canonical Shot dialogue."""
import re
from . import asset_roles

PREFIX = 'Speech and mouth movement: '
REFINEMENT_RULE = ('Preserve the draft speech and mouth-movement direction. Only canonical dialogue may '
    'appear inside <d> tags, exactly once per utterance, in order. Keep each speaker and timed window. '
    'On-screen speaking mouth movements must follow those words; other characters must not mouth them. '
    'For shots without dialogue, explicitly require no speech or speech-like mouth movements, while '
    'preserving specified breathing and other nonverbal actions. Do not add dialogue, narration or lyrics. ')


def direction(plan, shot, labels=None):
    names = {e['id']: e['name'] for e in plan['canon']}
    labels = labels or {}
    lines = shot['dialogue']
    if not lines:
        return (PREFIX + asset_roles.voice_direction(plan,shot,labels) + f'Throughout 0.00–{shot["duration"]:.2f}s, no character speaks. '
            'No dialogue, narration, whispered words or added vocal lyrics. '
            'No speech-like mouth movements; mouths rest naturally closed except for explicitly '
            'described nonverbal actions such as breathing or laughing. Preserve the specified acting and sound effects.')
    silent=[d for d in lines if d.get('delivery','').strip().lower() in {'無聲','只有口形，無聲','silent','inaudible','mouths silently'}]
    if silent:
        spoken=[d for d in lines if d not in silent]
        describe=lambda d:f'{labels.get(d["entity_id"],names[d["entity_id"]])} {d["start"]:.2f}–{d["end"]:.2f}s'
        return (PREFIX+asset_roles.voice_direction(plan,shot,labels)+'Silent articulation only, with no audible words, for '+ '; '.join(map(describe,silent))+'. Mouth the corresponding exact tagged words silently once. '+
                ('Audible scripted speech only for '+ '; '.join(map(describe,spoken))+'. ' if spoken else 'No audible dialogue in this Shot. ')+
                'All other characters remain non-speaking. Outside these windows, no speech-like mouth movement. Preserve specified nonverbal actions and sound effects; add no words or narration.')
    windows = '; '.join(
        f'{labels.get(d["entity_id"], names[d["entity_id"]])} {d["start"]:.2f}–{d["end"]:.2f}s'
        for d in lines)
    return (PREFIX + asset_roles.voice_direction(plan,shot,labels) + f'Speak only the scripted utterances, each exactly once, in these windows: {windows}. '
        'Use the exact words and language in the dialogue tags, with no additions, repetition or paraphrase. '
        'Whenever the speaker is visible, synchronize natural mouth articulation to those words and their timing. '
        'Other characters do not mouth the line. Outside each character\'s speaking windows, stop speech-like '
        'mouth movements and rest the mouth naturally closed, except for specified nonverbal actions. '
        'No added speech, narration or vocal lyrics; preserve the specified nonverbal sounds.')


def apply(text, plan, shot, labels=None, field='detailed_description:'):
    """Refresh our own single direction line without overwriting saved creative prose."""
    if field not in text:
        return text  # Existing structural validation reports the missing section.
    text = re.sub(r'^Speech and mouth movement: [^\n]*\n?', '', text, flags=re.M)
    before, _, body = text.partition(field)
    return before + field + '\n' + direction(plan, shot, labels) + '\n' + body.lstrip('\n')


def validate_dialogue(text, shot):
    # Reject additions and duplication as well as omissions, even if all original words survive.
    tagged = re.findall(r'<d>\s*\[[^\]\n]+\]\s*(.*?)\s*</d>', text, flags=re.S)
    expected = [d['text'].strip() for d in shot['dialogue']]
    if tagged != expected or text.count('<d>') != len(expected) or text.count('</d>') != len(expected):
        raise ValueError('Prompt must retain only the canonical dialogue, exactly once per utterance and in order')
