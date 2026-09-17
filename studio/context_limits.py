"""Frozen Studio budgets, distinct from advertised model training context.

Unknown tokenizers use a UTF-8 byte upper bound, never a claimed exact count.
llama.cpp requests use the selected gateway, including its VRAM admission rules.
"""
import json
from urllib.parse import urlsplit

import httpx

DEFAULTS = {'codex': (131072, 32768), 'deepseek': (1048576, 32768), 'http': (32768, 8192)}


def origin(provider):
    return provider['base_url'].rstrip('/').removesuffix('/v1')


def freeze(provider, probe=True):
    window, output = DEFAULTS.get(provider['kind'], (32768, 8192))
    window = provider.get('context_window') or window
    output = provider.get('max_output_tokens') or min(output, window // 4)
    policy = {'version': 'context-v1', 'context_window': window,
              'max_output_tokens': output, 'safety_tokens': 1024,
              'tokenizer': provider.get('tokenizer', 'estimate'),
              'origin': 'configured' if provider.get('context_window') else 'studio-budget'}
    if policy['tokenizer'] == 'llama_cpp' and probe:
        # Passive metadata only: the manager never loads Qwen for GET /props.
        try:
            r = httpx.get(origin(provider) + '/props', timeout=3)
            r.raise_for_status()
            runtime = r.json()['default_generation_settings']['n_ctx']
            if isinstance(runtime, int) and not isinstance(runtime, bool) and runtime > 0:
                policy['context_window'] = min(window, runtime)
                policy['origin'] += '+runtime-slot'
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            policy['origin'] += '+runtime-unavailable'
    if policy['context_window'] <= output + policy['safety_tokens']:
        raise ValueError('模型上下文容量不足以容納輸出預留；請調整服務商容量設定。')
    return policy


def estimate(text):
    return len(text.encode('utf-8'))


def measure(provider, text, policy):
    if policy['tokenizer'] != 'llama_cpp':
        return estimate(text)
    try:
        with httpx.Client(timeout=15, headers={'X-VRAM-Wait-Seconds': '0'}) as client:
            r = client.post(origin(provider) + '/apply-template', json={
                'messages': [{'role': 'user', 'content': text}]})
            r.raise_for_status()
            rendered = r.json()['prompt']
            if not isinstance(rendered, str):
                raise ValueError('Invalid chat template')
            r = client.post(origin(provider) + '/tokenize', json={'content': rendered, 'add_special': True})
            r.raise_for_status()
            tokens = r.json()['tokens']
            if not isinstance(tokens, list) or not all(isinstance(t, int) for t in tokens):
                raise ValueError('Invalid tokenizer result')
            # The service may have restarted with a smaller per-slot context
            # since this job froze its policy. Refuse before any generation.
            r = client.get(origin(provider) + '/props')
            r.raise_for_status()
            runtime = r.json()['default_generation_settings']['n_ctx']
            if not isinstance(runtime, int) or isinstance(runtime, bool) or runtime < policy['context_window']:
                raise ValueError('Runtime context differs from frozen budget')
            return len(tokens)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise ValueError('未能經所選服務商核對 token 數；本機可能忙碌，請稍後接續。未截斷背景或切換模型。') from None


def wire_text(prompt, schema):
    # Keep this identical to the HTTP adapter, including JSON schema whitespace.
    return prompt + '\nReturn JSON matching this schema: ' + json.dumps(schema)


def count(provider, prompt, schema, policy):
    return measure(provider, wire_text(prompt, schema), policy)


def input_count_label(tokens, method):
    # Distinguish a conservative UTF-8 byte upper bound from a native measured token count.
    if method == 'chat-template-tokenizer':
        return f'實際核對 {tokens:,} tokens'
    return f'UTF-8 位元組保守上界 {tokens:,}（非精確 token 數）'


def overflow_error(tokens, method, policy):
    # Retain the actionable preservation text after the clarified measurement label.
    return (f'必要上下文超出所選模型預算（輸入{input_count_label(tokens, method)}，'
            f'預留輸出 {policy["max_output_tokens"]}，容量 {policy["context_window"]}）；'
            '已保存成果保留，未截斷原文或切換服務商。')


def fits(tokens, policy):
    return tokens + policy['max_output_tokens'] + policy['safety_tokens'] <= policy['context_window']


def check(provider, prompt, schema, work=None):
    policy = provider.get('context_policy')
    if not policy:
        return None  # Existing frozen jobs retain their legacy transport contract.
    tokens = count(provider, prompt, schema, policy)
    receipt = {'policy': policy, 'input_tokens': tokens,
               'count_method': 'chat-template-tokenizer' if policy['tokenizer'] == 'llama_cpp' else 'utf8-byte-upper-bound',
               'fits': fits(tokens, policy)}
    if work is not None:
        from .chapter_pipeline import atomic_json
        atomic_json(work / 'context-budget.json', receipt)
    if not receipt['fits']:
        raise ValueError(overflow_error(tokens, receipt['count_method'], policy))
    return receipt


def receipt(job):
    """Expose only numeric root-attempt accounting, including historical jobs."""
    from . import store
    work = store.DATA / 'jobs' / job['id']
    def read(name):
        try:
            value = json.loads((work / name).read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}
    def number(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    budget, transport = read('context-budget.json'), read('transport.json')
    if not budget and not transport:
        return None
    usage = transport.get('usage')
    usage = usage if isinstance(usage, dict) else {}
    return {'input_tokens': number(budget.get('input_tokens')),
            'count_method': budget.get('count_method') if budget.get('count_method') in ('chat-template-tokenizer', 'utf8-byte-upper-bound') else None,
            'fits': budget.get('fits') if isinstance(budget.get('fits'), bool) else None,
            'content_chars': number(transport.get('content_chars')),
            'reasoning_chars': number(transport.get('reasoning_chars')),
            'finish_reason': transport.get('finish_reason') if transport.get('finish_reason') in ('stop', 'length') else None,
            'usage': {key: number(usage.get(key)) for key in ('prompt_tokens', 'completion_tokens', 'reasoning_tokens')}}
