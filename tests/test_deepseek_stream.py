import json

import httpx
import pytest

from studio import providers, deepseek_stream


class Bytes(httpx.SyncByteStream):
    def __init__(self, chunks, error=None, after=None):
        self.chunks, self.error, self.after = chunks, error, after

    def __iter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.after:
            self.after()
        if self.error:
            raise self.error


def event(text=None, finish=None, **delta):
    if text is not None:
        delta['content'] = text
    return ('data: ' + json.dumps({'choices': [{'index': 0, 'delta': delta, 'finish_reason': finish}]}, ensure_ascii=False) + '\n\n').encode()


def setup(monkeypatch, chunks, error=None, after=None):
    seen = []
    real = httpx.Client
    def handler(request):
        seen.append(request)
        return httpx.Response(200, headers={'content-type': 'text/event-stream; charset=utf-8'}, stream=Bytes(chunks, error, after))
    monkeypatch.setattr(providers.httpx, 'Client', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr('studio.provider_profiles.credential_value', lambda key: 'test-secret')
    monkeypatch.setattr(providers, 'codex_run', lambda *a: pytest.fail('No fallback'))
    return seen


def run(work):
    return providers.run({'kind': 'deepseek', 'model': 'test', 'vision_model': 'vision-test', 'key_env': 'KEY', 'base_url': 'https://example.test'}, 'h3', 'Return JSON', [], work)


def test_success_split_utf8_keepalive_reasoning_usage(monkeypatch, tmp_path):
    raw = b': keep-alive\n\n' + event(reasoning_content='PRIVATE REASONING') + event('{"text":"天') + event('水圍"}', 'stop') + b'data: {"choices":[],"usage":{}}\n\ndata: [DONE]\n\n'
    seen = setup(monkeypatch, [raw[i:i+1] for i in range(len(raw))])
    assert run(tmp_path) == {'text': '天水圍'}
    assert len(seen) == 1 and json.loads(seen[0].content)['stream'] is True
    assert (tmp_path/'result.json').read_text() == '{"text":"天水圍"}'
    assert (tmp_path/'provider-partial.txt').read_text() == '{"text":"天水圍"}'
    diag = json.loads((tmp_path/'transport.json').read_text())
    assert diag['status'] == 'complete' and diag['done']
    assert diag['content_chars'] == len('{"text":"天水圍"}')
    assert all('PRIVATE REASONING' not in p.read_text() and 'test-secret' not in p.read_text() for p in tmp_path.iterdir())


@pytest.mark.parametrize('kind', ['protocol', 'timeout', 'eof', 'no_stop', 'length', 'bad_event'])
def test_incomplete_never_saved_as_result(monkeypatch, tmp_path, kind):
    chunks = [event('{"text":"partial"}')]
    error = None
    if kind == 'protocol': error = httpx.RemoteProtocolError('test-secret PRIVATE-RAW')
    if kind == 'timeout': error = httpx.ReadTimeout('test-secret PRIVATE-RAW')
    if kind == 'no_stop': chunks += [b'data: [DONE]\n\n']
    if kind == 'length': chunks += [event(finish='length'), b'data: [DONE]\n\n']
    if kind == 'bad_event': chunks += [b'data: {bad PRIVATE-RAW}\n\n']
    seen = setup(monkeypatch, chunks, error)
    with pytest.raises(RuntimeError) as exc:
        run(tmp_path)
    assert 'PRIVATE-RAW' not in str(exc.value) and 'test-secret' not in str(exc.value)
    assert len(seen) == 1
    assert not (tmp_path/'result.json').exists()
    assert not (tmp_path/'provider-output.txt').exists()
    assert (tmp_path/'provider-partial.txt').read_text() == '{"text":"partial"}'
    diag = (tmp_path/'transport.json').read_text()
    assert 'PRIVATE-RAW' not in diag and 'test-secret' not in diag


def test_complete_invalid_schema_saved_for_correction(monkeypatch, tmp_path):
    setup(monkeypatch, [event('{}', 'stop'), b'data: [DONE]\n\n'])
    with pytest.raises(ValueError): run(tmp_path)
    assert (tmp_path/'result.json').read_text() == '{}'


@pytest.mark.parametrize('where', ['work', 'parent'])
def test_cancel_at_end_does_not_save_result(monkeypatch, tmp_path, where):
    work = tmp_path/'attempt'
    setup(monkeypatch, [event('{"text":"ok"}', 'stop')], after=lambda: ((work if where=='work' else tmp_path)/'cancel-requested').touch())
    with pytest.raises(RuntimeError, match='取消'): run(work)
    assert not (work/'result.json').exists()


def test_deadline_on_live_stream(monkeypatch, tmp_path):
    now = [0]
    monkeypatch.setattr(deepseek_stream.time, 'monotonic', lambda: now[0])
    setup(monkeypatch, [event('{"text":"ok"}', 'stop')], after=lambda: now.__setitem__(0, 901))
    with pytest.raises(RuntimeError, match='15 分鐘'): run(tmp_path)
    assert not (tmp_path/'result.json').exists()


def test_reasoning_exhaustion_accounts_budget_without_storing_reasoning(monkeypatch, tmp_path):
    usage = {'completion_tokens':32768,'completion_tokens_details':{'reasoning_tokens':32768},'private':'SECRET'}
    chunks = [event(reasoning_content='PRIVATE REASONING'),event(finish='length'),
              ('data: '+json.dumps({'choices':[], 'usage':usage})+'\n\ndata: [DONE]\n\n').encode()]
    seen=setup(monkeypatch,chunks)
    provider={'kind':'deepseek','model':'test','key_env':'KEY','base_url':'https://example.test',
              'context_policy':{'max_output_tokens':32768,'context_window':1048576,'safety_tokens':1024,'tokenizer':'estimate'}}
    with pytest.raises(RuntimeError,match='推理階段已達上限'):
        providers.run(provider,'h3','Return JSON',[],tmp_path)
    payload=json.loads(seen[0].content)
    assert payload['max_tokens']==32768 and payload['stream_options']['include_usage']
    diag=json.loads((tmp_path/'transport.json').read_text())
    assert diag['usage']=={'completion_tokens':32768,'reasoning_tokens':32768}
    assert diag['reasoning_chars']==len('PRIVATE REASONING') and diag['content_chars']==0
    assert diag['requested_max_tokens']==32768
    assert len(seen)==1 and not (tmp_path/'result.json').exists()
    assert all('PRIVATE REASONING' not in f.read_text() and 'SECRET' not in f.read_text() for f in tmp_path.iterdir())
