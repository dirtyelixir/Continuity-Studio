"""Assemble LoRA activation prefixes without editing saved creative prompts."""
import re
from . import h3_lora_catalog


def assemble(source, settings):
    adapters = ([{'name': settings['acceleration_lora'], 'strength': 1.0}]
                if settings.get('acceleration_lora') else []) + settings.get('other_loras', [])
    records, triggers = [], []
    for adapter in adapters:
        preset = h3_lora_catalog.preset(adapter['name'])
        trigger = preset.get('trigger', '').strip()
        records.append({**adapter, 'trigger': trigger, 'source_url': preset.get('source_url', '')})
        if trigger and trigger.casefold() not in [x.casefold() for x in triggers]:
            triggers.append(trigger)
    text, common = source['text'], source.get('global_prompt', '')
    target = 'global_prompt' if source['mode'] == 'REF2VA' and common.strip() else 'text'
    original = common if target == 'global_prompt' else text
    # Recognize only a leading activation block; dialogue/body occurrences do not count.
    remaining, existing = original, set()
    while triggers:
        found = False
        for trigger in triggers:
            match = re.match(r'^\s*' + re.escape(trigger) + r'(?=$|[\s,;])[\s,;]*', remaining, re.I)
            if match:
                existing.add(trigger.casefold())
                remaining = remaining[match.end():]
                found = True
                break
        if not found:
            break
    added = [t for t in triggers if t.casefold() not in existing]
    result = ('; '.join(added) + '\n\n' if added else '') + original
    if target == 'global_prompt':
        common = result
    else:
        text = result
    return {'version': 1, 'text': text, 'global_prompt': common,
            'prefix_target': target, 'triggers': triggers, 'added_triggers': added, 'loras': records}


def generation_source(source, assembly):
    return {**source, 'text': assembly['text'], 'global_prompt': assembly['global_prompt']}
