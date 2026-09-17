"""Shared prompt-writing judgment, loaded from the versioned Studio method bundle.

Why this module exists
----------------------
Prompt quality was previously spread over a dozen inline instruction constants plus the
``studio-production-methods`` bundle, and the agent-facing skill package carried a hand-made copy
of that bundle. Writers therefore drifted apart, and the same craft rule could be missing from one
entry point and duplicated in another.

This module is the single runtime reading of the shared writing principles:

* the prose lives once, in ``references/prompt-writing.md`` of the Studio method bundle, which is
  content-hashed and routed per capability, so every capability that writes a prompt receives it
  through the existing ``production_methods.snapshot`` injection;
* the per-task contract lives once, in ``references/prompt-tasks.json`` of the same bundle;
* agents receive the same files through the skill package, regenerated from this source by
  ``scripts/export_skill_package.py`` and checked by ``tests/test_skill_package_sync.py``, so there
  is exactly one copy to maintain.

Scope and limits
----------------
The checks below are deliberately mechanical. They catch faults a program can prove: syntax the
target does not support, a reference slot that does not exist, a crop that contradicts itself,
sequential action inside a frozen instants, a state restated until it means nothing, or emphasis
inflated into noise. They do **not** judge composition, performance or emotional quality — those
belong to the existing review paths, and pretending a keyword rule can settle them would be worse
than saying so.

Nothing here may change canonical state, approve, adopt or regenerate anything. The module reads
text and reports findings; every decision stays where it already lives.

Public API
----------
``principles()``                      -> shared writing principles (prose)
``task(kind)``                        -> per-task contract dict
``task_for_image(kind, moment, operation)`` / ``task_for_video(mode)``
``guidance(kind)``                    -> principles + this task's contract, for model instructions
``finding_text(findings)``            -> stable one-line rendering of findings
``check(fields, kind, ...)``          -> (findings, blocking) deterministic review
``CHECK_CODES`` / ``SUPPORTED_TASKS``
"""

from __future__ import annotations

import json
import re

from . import production_methods

PRINCIPLES_FILE = 'prompt-writing.md'
TASKS_FILE = 'prompt-tasks.json'

CHECK_CODES = (
    'unsupported_syntax',        # weighting / negative field / timing the target will read as text
    'reference_slot_missing',    # a numbered reference that was never supplied (blocking)
    'reference_overreach',       # inheriting a state the reference role does not own
    'still_action_leak',         # sequential action inside one frozen instant
    'composition_conflict',      # mutually exclusive framing or visibility demands (blocking)
    'ownership_ambiguity',       # an action clause without a named actor
    'cause_ambiguity',           # emission with no stated source
    'state_duplication',         # one declared state restated across sections
    'over_escalation',           # emphasis inflation instead of specification
    'redundancy',                # repeated description spending attention without adding control
)

BLOCKING_CODES = frozenset({'unsupported_syntax', 'reference_slot_missing', 'composition_conflict'})

_UNSUPPORTED = (
    (re.compile(r'\(\s*[^():]{1,40}:\s*\d+(?:\.\d+)?\s*\)'), 'attention weighting "(term:1.2)"'),
    (re.compile(r'\[[^\]\n]{1,30}:\s*\d+(?:\.\d+)?\]'), 'attention weighting "[term:1.2]"'),
    (re.compile(r'\bnegative\s*prompt\b|\b--no\b|\b--neg\b', re.I), 'a negative-prompt field'),
    (re.compile(r'(?:^|[\s(])(?:\d+(?:\.\d+)?)s?\s*[-–]\s*\d+(?:\.\d+)?s?\s*:'), 'a timed directive'),
)

_STILL_TASKS = frozenset({'still_frame', 'exact_start_keyframe', 'portrait', 'prop_design',
                          'location_plate', 'character_sheet', 'image_edit'})

_SEQUENTIAL = re.compile(
    r'\b(?:and\s+then|then|after\s+which|followed\s+by|subsequently|begins? to|starts? to|'
    r'about\s+to|is\s+going\s+to|next\s+she|next\s+he)\b', re.I)

_EMISSION = re.compile(r'\b(glow|glowing|glows|lit|lighting up|emits?\s+light|radiant|'
                       r'illuminat\w*|flame|filament\s+glow|shines?|shining)\b', re.I)
_LIGHT_SOURCE = re.compile(r'\b(sconce|lamp|lantern|window|sunlight|daylight|moonlight|fire|'
                           r'candle|torch|screen|monitor|neon|sign|headlight|projector|'
                           r'reflect\w*|bounce|bounced|spill\w*)\b', re.I)

_PRONOUN = re.compile(r'\b(he|she|they|him|her|them|his|hers|their|theirs|it|its)\b', re.I)
_NAMED = re.compile(r'<Entity [^>]+>|\b[A-Z][a-z]{2,}\b')

_EMPHASIS = re.compile(r'\b(CRITICAL|MANDATORY|MUST|NEVER|ALWAYS|DO\s+NOT|violat\w*|'
                       r'if\s+incorrect|fail\s+the\s+image)\b')

_HIDDEN = re.compile(r'\b(hidden|occluded|out\s+of\s+view|not\s+visible|off-?screen|'
                     r'removed\s+from\s+view|concealed)\b', re.I)
_VISIBLE = re.compile(r'\b(clearly\s+visible|fully\s+visible|legible|readable|plainly\s+seen|'
                      r'in\s+clear\s+view|clearly\s+readable)\b', re.I)
_CLOSE = re.compile(r'\b(extreme\s+close-?up|macro|tight\s+close-?up)\b', re.I)
_WIDE = re.compile(r'\b(wide\s+shot|wide\s+angle|establishing\s+shot|full\s+body)\b', re.I)
_SHALLOW = re.compile(r'\b(shallow\s+(?:depth\s+of\s+field|focus)|bokeh|blurred\s+background|'
                      r'out-?of-?focus\s+background)\b', re.I)
_FINE_DETAIL = re.compile(r'\b(small|tiny|distant|background|far)\b'
                          r'[^.;]{0,80}?(?:clearly\s+visible|legible|readable|sharp\s+detail)', re.I)
_CROP_CONFLICT = (
    (re.compile(r'\b(cropped?\s+at\s+the\s+waist|cropped?\s+at\s+the\s+hips)\b', re.I),
     re.compile(r'\bfull\s+body\b|\bhead\s+to\s+toe\b', re.I), 'crop contradicts full body'),
)

# Words that carry no subject of their own, so they cannot be the thing that is both hidden and shown.
_NOT_A_SUBJECT = frozenset("""
about above across after again against along also although always and another any are around
because been before behind being below beneath beside besides between beyond both but camera
careful carefully clearly close complete completely composition continuous correct correctly do
does done down during each edge either enough even ever every exactly face facing far few first
for found from fully further generally given great here hidden high however into itself just keep
kept large last later left less light like long made make many may might more most much must near
nearly necessary never next no none nor not nothing now only onto opposite other others out over
own part particular past perhaps place please possible precisely present probably quite rather
readable really remain remains right same seen several shall sharp should shown shows similar
simply since slightly small some something sometimes soon still such sure than that their them
then there these they thing things this those though through thus time together too toward towards
under until upon very view visible well were what when where whether which while whole whose will
with within without would your
""".split())


def _subject_near(text, position, back=5, ahead=1):
    """The head noun this visibility claim is about: nearest word before it, else just after.

    A phrase such as "the toggle remains unoccluded and clearly visible" binds one subject, while
    "Ada stands behind the bench, the toggle clearly visible" binds two different ones. Only a
    shared subject is a real conflict, so the claim has to be resolved to its own noun.
    """
    before = re.findall(r"[A-Za-z][A-Za-z'-]+", text[max(0, position - 90):position])
    for word in reversed(before[-back:]):
        lowered = word.lower()
        if lowered not in _NOT_A_SUBJECT and len(lowered) > 2 and lowered not in ('the', 'its', 'her', 'his'):
            return lowered
    after = re.findall(r"[A-Za-z][A-Za-z'-]+", text[position:position + 60])
    for word in after[:ahead]:
        lowered = word.lower()
        if lowered not in _NOT_A_SUBJECT and len(lowered) > 2 and lowered not in ('the', 'its', 'her', 'his'):
            return lowered
    return ''


def _visibility_conflict(text):
    """A subject demanded to be both out of view and clearly visible — mechanically provable."""
    hidden = {_subject_near(text, m.start()) for m in _HIDDEN.finditer(text)}
    visible = {_subject_near(text, m.start()) for m in _VISIBLE.finditer(text)}
    return sorted((hidden & visible) - {''})
_REFERENCE_STATE = re.compile(
    r'\b(?:inherit|inherit\w*|copy|carry\s+over|take)\b[^.;]{0,60}'
    r'\b(?:illumination|light\s*state|switch|power|on/?off|lit|unlit|toggle\s+state)\b', re.I)

_STATE_WORDS = ('off', 'unlit', 'switched off', 'dark', 'powered down', 'inactive')


def _bundle_text(name):
    return production_methods.reference(name)


def principles():
    """The shared writing principles, identical for every writer and every agent."""
    return _bundle_text(PRINCIPLES_FILE).strip()


def _tasks():
    return json.loads(_bundle_text(TASKS_FILE))


def supported_tasks():
    return sorted(_tasks()['tasks'])


def task(kind):
    """Per-task contract. Unknown kinds degrade to the shared principles alone."""
    entry = _tasks()['tasks'].get(kind)
    if entry is None:
        return {'kind': kind, 'emphasis': [], 'checks': list(CHECK_CODES),
                'syntax': {'weighting': False, 'negative_prompt': False, 'timing_directives': False}}
    return {'kind': kind, **entry}


def task_for_image(target_kind, moment=None, operation=None):
    """Map an image target/operation onto a writing task. Deterministic, no guessing."""
    if operation and operation not in ('auto', 'new', 'reference'):
        return 'image_edit'
    return {'character': 'character_sheet', 'location': 'location_plate', 'prop': 'prop_design',
            'frame': 'exact_start_keyframe' if moment == 'start' else 'still_frame'}.get(
        target_kind, 'still_frame')


def task_for_video(mode):
    return {'I2VA': 'video_i2va', 'FL2VA': 'video_fl2va', 'REF2VA': 'video_ref2va'}.get(
        str(mode).upper(), 'video_ref2va')


def contract_line(kind):
    """One compact line restating this task's own obligations."""
    entry = task(kind)
    bits = []
    if entry.get('positive'):
        bits.append('This task: ' + entry['positive'] + '.')
    if entry.get('preserve'):
        bits.append('Keep: ' + '; '.join(entry['preserve']) + '.')
    if entry.get('forbid'):
        bits.append('Do not: ' + '; '.join(entry['forbid']) + '.')
    if entry.get('requires_fields'):
        bits.append('State the delta explicitly in: ' + ', '.join(entry['requires_fields']) + '.')
    return ' '.join(bits)


def guidance(kind=None):
    """Principles plus the optional task contract, for injection into a model instruction."""
    parts = ['SHARED PROMPT-WRITING METHOD (Studio-owned, applies to every prompt you write):',
             principles()]
    if kind:
        line = contract_line(kind)
        if line:
            parts.append('TASK CONTRACT (' + kind + '):\n' + line)
    return '\n\n'.join(parts)


def _texts(fields):
    if isinstance(fields, str):
        return [('text', fields)]
    out = []
    for key, value in (fields or {}).items():
        if isinstance(value, str) and value.strip():
            out.append((key, value))
    return out


def _reference_index_findings(joined):
    supplied = None
    findings = []
    for match in re.finditer(r'\bImage\s+(\d+)\b', joined):
        index = int(match.group(1))
        supplied = max(supplied or 0, index)
    return findings, supplied


def check(fields, kind=None, reference_count=None, declared_states=()):
    """Deterministic review of written prompt text.

    Returns ``(findings, blocking)``. A finding is
    ``{'code', 'severity', 'detail', 'evidence'}``. Only :data:`BLOCKING_CODES` may block, and
    only when the fault is mechanically provable; everything else is advisory and is recorded
    rather than enforced. Missing information is never reported as a fault.
    """
    texts = _texts(fields)
    joined = '\n'.join(text for _, text in texts)
    findings = []

    def add(code, detail, evidence, blocking=None):
        hard = code in BLOCKING_CODES if blocking is None else blocking
        findings.append({'code': code, 'severity': 'blocking' if hard else 'advisory',
                         'detail': detail, 'evidence': evidence.strip()[:160]})

    # 1. syntax the target will read as ordinary text rather than as control
    for pattern, label in _UNSUPPORTED:
        match = pattern.search(joined)
        if match:
            add('unsupported_syntax', 'This renderer has no %s; it will be read as literal text. '
                                      'Express the requirement in positive, visible words instead.' % label,
                match.group(0))

    # 2. reference slots that were never supplied
    _, highest = _reference_index_findings(joined)
    if reference_count is not None and highest and highest > int(reference_count):
        add('reference_slot_missing',
            'Text cites Image %d but only %d reference images were supplied.' % (highest, reference_count),
            'Image %d' % highest)

    # 3. inheriting a state the reference role does not own
    match = _REFERENCE_STATE.search(joined)
    if match:
        add('reference_overreach', 'A reference image is being asked to decide a switch, power or '
                                   'illumination state. A design or identity reference does not '
                                   'carry the current state.', match.group(0))

    # 4. sequential action inside a frozen instant
    if kind in _STILL_TASKS:
        match = _SEQUENTIAL.search(joined)
        if match:
            add('still_action_leak', 'A still frame describes more than one instant ("%s"). State the '
                                     'single frozen moment; leave the following action out.'
                % match.group(0), _clause(joined, match.start()))

    # 5. framing or visibility demands that cannot both hold
    # Provable conflicts block; the softer scale and focus combinations are reported only, because a
    # prompt can legitimately name a focal plane and still keep one foreground detail readable.
    close_hit, wide_hit = _CLOSE.search(joined), _WIDE.search(joined)
    if close_hit and wide_hit:
        add('composition_conflict', 'The same frame is asked for both a close/macro scale and a wide '
                                    'or full-body scale; one of them has to give.', _clause(joined, wide_hit.start()),
            blocking=False)
    shallow_hit, fine_hit = _SHALLOW.search(joined), _FINE_DETAIL.search(joined)
    if shallow_hit and fine_hit:
        add('composition_conflict', 'Shallow focus is requested together with legibility of a small '
                                    'or distant detail; check the audience can still read it.',
            _clause(joined, fine_hit.start()), blocking=False)
    for left, right, label in _CROP_CONFLICT:
        if left.search(joined) and right.search(joined):
            add('composition_conflict', 'Framing contradicts itself: ' + label + '.', label)
    for subject in _visibility_conflict(joined):
        add('composition_conflict', '"%s" is required to be out of view and clearly visible at the '
                                    'same time.' % subject, subject)

    # 6. an action clause whose actor could be either of two people
    # Only a genuinely unresolvable clause is reported: two different third-person pronouns acting in
    # one clause with no name to settle it ("he hands it to her" is fine; "he takes it, then she
    # takes it" in one clause is not). Established subjects earlier in a field are not an ambiguity.
    if kind in _STILL_TASKS or kind in ('shot_prompt', 'scene_global', 'video_ref2va'):
        for clause in re.split(r'[;.]', joined):
            clause = clause.strip()
            pronouns = {p.lower() for p in _PRONOUN.findall(clause)}
            masculine = pronouns & {'he', 'him', 'his'}
            feminine = pronouns & {'she', 'her', 'hers'}
            if not (masculine and feminine):
                continue
            if _NAMED.search(clause):
                continue
            add('ownership_ambiguity', 'One clause uses both "he/his" and "she/her" with no name to '
                                       'settle which person acts or owns what.', clause)
            break

    # 7. emission with no stated source anywhere in the text
    if _EMISSION.search(joined) and not _LIGHT_SOURCE.search(joined):
        add('cause_ambiguity', 'The text asks for light or glow but never says what produces it, so '
                               'the generator will invent a source.', _clause(joined, _EMISSION.search(joined).start()))

    # 8. one declared state restated until it carries no weight
    for state in declared_states or ():
        lowered = str(state).strip().lower()
        if not lowered:
            continue
        hits = sum(1 for _, text in texts if lowered[:12] and lowered[:12] in text.lower())
        if hits > 2:
            add('state_duplication', 'The declared state "%s" is restated in %d sections. Say it once, '
                                     'clearly; repetition spends attention without adding control.'
                % (state, hits), str(state))
        break

    # 9. emphasis used in place of specification
    emphasis = _EMPHASIS.findall(joined)
    if len(emphasis) > 3:
        add('over_escalation', 'Emphasis words (%s) appear %d times. Prefer specific visible '
                               'requirements; shouting is not enforcement.'
            % (', '.join(sorted({e.upper() if isinstance(e, str) else e for e in emphasis}))[:60],
               len(emphasis)), emphasis[0])

    # 10. the same description repeated
    repeated = _repeated_phrase(joined)
    if repeated:
        add('redundancy', 'The phrase "%s" is repeated; it spends attention without adding control.'
            % repeated[0], repeated[1])

    blocking = [f for f in findings if f['severity'] == 'blocking']
    return findings, blocking


def _clause(text, position, width=90):
    start = max(0, position - width // 2)
    return text[start:start + width].replace('\n', ' ').strip()


def _repeated_phrase(text):
    """A 7-word phrase repeated three or more times verbatim: genuinely redundant, not just reused.

    Prompts legitimately refer to the same object more than once, so a single reuse is not reported;
    only phrasing repeated until it spends attention without adding control.
    """
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < 120:
        return ()
    counts = {}
    for i in range(len(words) - 7):
        gram = ' '.join(words[i:i + 7])
        counts[gram] = counts.get(gram, 0) + 1
    for gram, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        if count >= 3:
            return gram, 'x%d' % count
    return ()


def finding_text(findings):
    """Stable one-line rendering for logs, job notes and receipts."""
    return '; '.join('%s[%s]: %s' % (f['code'], f['severity'], f['detail']) for f in findings)
