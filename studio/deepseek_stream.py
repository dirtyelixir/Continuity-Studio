"""DeepSeek chat transport: preserve partial evidence, require complete output."""
import json
import time

import httpx


def receive(client, url, headers, payload, work):
    started = time.monotonic()
    diag = {'status': 'receiving', 'http_status': None, 'lines': 0,
            'content_chunks': 0, 'content_chars': 0, 'done': False,
            'finish_reason': None, 'error_class': None,
            'requested_max_tokens': payload.get('max_tokens'),
            'reasoning_chunks': 0, 'reasoning_chars': 0, 'usage': {}}
    output = []
    finish = None
    done = False

    def persist():
        diag['elapsed_seconds'] = round(time.monotonic() - started, 3)
        # Only locally defined labels/counters; never response headers or errors.
        temp = work / 'transport.json.tmp'
        temp.write_text(json.dumps(diag, ensure_ascii=False))
        temp.replace(work / 'transport.json')

    def guard():
        if any((p / 'cancel-requested').is_file() for p in (work, work.parent)):
            diag['status'] = 'cancelled'
            raise RuntimeError('使用者已取消工作。')
        if time.monotonic() - started >= 900:
            diag['status'] = 'timeout'
            raise RuntimeError('DeepSeek 回應超過 15 分鐘，本階段已停止；可接續未完成階段。')

    def account(message=None, usage=None):
        reasoning = (message or {}).get('reasoning_content')
        if isinstance(reasoning, str) and reasoning:
            diag['reasoning_chunks'] += 1
            diag['reasoning_chars'] += len(reasoning)
        # Keep numeric accounting only, never private reasoning or arbitrary fields.
        if isinstance(usage, dict):
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                value = usage.get(key)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    diag['usage'][key] = value
            details = usage.get('completion_tokens_details')
            value = details.get('reasoning_tokens') if isinstance(details, dict) else None
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                diag['usage']['reasoning_tokens'] = value

    def append(text, partial):
        if not isinstance(text, str):
            raise ValueError('Invalid content type')
        output.append(text)
        partial.write(text)
        partial.flush()
        diag['content_chunks'] += 1
        diag['content_chars'] += len(text)

    try:
        guard()
        persist()
        with (work / 'provider-partial.txt').open('w', encoding='utf-8') as partial:
            with client.stream('POST', url, headers=headers, json={**payload, 'stream': True, 'stream_options': {'include_usage': True}}) as response:
                diag['http_status'] = response.status_code
                persist()
                response.raise_for_status()
                guard()
                if 'application/json' in response.headers.get('content-type', ''):
                    # Complete JSON from compatible endpoints; never resubmit.
                    response.read()
                    guard()
                    document = response.json()
                    choice = document['choices'][0]
                    account(choice.get('message'), document.get('usage'))
                    append(choice.get('message', {}).get('content') or '', partial)
                    finish = choice.get('finish_reason')
                    done = True
                else:
                    for line in response.iter_lines():
                        guard()
                        diag['lines'] += 1
                        if not line.startswith('data:'):
                            continue  # blank lines and SSE keep-alive comments
                        data = line[5:].strip()
                        if data == '[DONE]':
                            done = True
                            break
                        event = json.loads(data)
                        if 'error' in event:
                            raise ValueError('Provider error event')
                        account(usage=event.get('usage'))
                        choices = event.get('choices', [])
                        if not choices:
                            continue  # usage-only event
                        choice = choices[0]
                        if choice.get('index', 0) != 0:
                            raise ValueError('Unexpected choice index')
                        delta = choice.get('delta') or {}
                        if delta.get('content'):
                            append(delta['content'], partial)
                        account(delta)  # Count reasoning, never retain its text.
                        if choice.get('finish_reason') is not None:
                            finish = choice['finish_reason']
                        persist()
                guard()
        diag['done'] = done
        diag['finish_reason'] = finish if finish in ('stop', 'length', 'content_filter', 'tool_calls') else 'unknown'
        if finish == 'length':
            diag['status'] = 'truncated'
            limit = diag['requested_max_tokens']
            budget = f'（本次上限 {limit:,} tokens）' if isinstance(limit, int) else ''
            detail = '推理階段已達上限，尚未產生正式答案。' if diag['reasoning_chars'] and not diag['content_chars'] else '未取得完整答案。'
            raise RuntimeError(f'DeepSeek 輸出達到長度上限{budget}；{detail}請查看輸出預算；增加上下文容量不會自動增加輸出額度。')
        if not done or finish != 'stop':
            diag['status'] = 'incomplete'
            raise RuntimeError('DeepSeek 回應未完整結束；已保留收到的部分文字供診斷，可接續未完成階段。')
        if not ''.join(output).strip():
            diag['status'] = 'empty'
            raise RuntimeError('DeepSeek 回傳內容為空；未保存為完整結果。')
        diag['status'] = 'complete'
        return {'message': {'content': ''.join(output)}, 'finish_reason': finish}
    except httpx.TimeoutException as exc:
        diag.update(status='timeout', error_class=type(exc).__name__)
        raise RuntimeError('等待 DeepSeek 回應逾時；已保留收到的部分文字供診斷，可接續未完成階段。') from None
    except httpx.HTTPStatusError as exc:
        diag.update(status='http_error', error_class=type(exc).__name__)
        raise RuntimeError(f'DeepSeek 回傳 HTTP {diag["http_status"]}，本階段未完成；請檢查服務狀態及帳戶設定。') from None
    except httpx.TransportError as exc:
        diag.update(status='disconnected', error_class=type(exc).__name__)
        raise RuntimeError('DeepSeek 回應傳輸中斷；可能是服務商或中途網路設備關閉連線。已保留收到的部分文字供診斷，可接續未完成階段。') from None
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        diag.update(status='invalid_response', error_class=type(exc).__name__)
        raise RuntimeError('DeepSeek 傳輸內容格式異常；未保存為完整結果，可接續未完成階段。') from None
    finally:
        persist()
