import json
import httpx
import pytest
from studio import context_limits as limits, models, providers, store, engine
from test_production import client, plan


def test_explicit_budgets_and_conservative_counter():
    p={'kind':'http','context_window':16384,'max_output_tokens':4096}
    frozen=limits.freeze(p)
    assert frozen['context_window']==16384 and frozen['max_output_tokens']==4096
    assert frozen['origin']=='configured'
    assert limits.estimate('伏筆🔑')==len('伏筆🔑'.encode())
    assert limits.freeze({'kind':'http'})['context_window']==32768
    with pytest.raises(ValueError):limits.freeze({**p,'context_window':4096})


@pytest.mark.parametrize('extra',[{'context_window':2048},{'max_output_tokens':0},{'context_window':8192,'max_output_tokens':8192}])
def test_provider_rejects_unusable_limits(extra):
    with pytest.raises(ValueError):models.ProviderConfig.model_validate({'id':'p','name':'p','kind':'http','model':'p','capabilities':['narrative'],**extra})


def test_passive_runtime_slot_limit_and_unavailable_metadata(monkeypatch):
    provider={**providers.LOCAL_QWEN,'context_window':131072}
    monkeypatch.setattr(limits.httpx,'get',lambda url,**kw:httpx.Response(200,json={'default_generation_settings':{'n_ctx':32768}},request=httpx.Request('GET',url)))
    p=limits.freeze(provider)
    assert p['context_window']==32768 and p['origin']=='configured+runtime-slot'
    def unavailable(*a,**kw):raise httpx.ConnectError('unavailable')
    monkeypatch.setattr(limits.httpx,'get',unavailable)
    assert limits.freeze(provider)['origin']=='configured+runtime-unavailable'
    assert limits.freeze(provider,probe=False)['context_window']==131072


@pytest.mark.parametrize('failure',[None,'tokenizer','smaller_runtime'])
def test_exact_chat_template_count_uses_selected_gateway(monkeypatch,failure):
    real=httpx.Client;seen=[]
    def handler(request):
        seen.append(request)
        assert request.url.host=='127.0.0.1' and request.url.port==8080
        assert request.headers['X-VRAM-Wait-Seconds']=='0'
        if request.url.path=='/apply-template':
            assert json.loads(request.content)['messages'][0]['content']=='現在去取鎖匙。'
            return httpx.Response(200,json={'prompt':'<user>現在去取鎖匙。</user>'})
        if request.url.path=='/tokenize':
            assert json.loads(request.content)['content'].startswith('<user>')
            return httpx.Response(503 if failure=='tokenizer' else 200,json={'tokens':[1,2,3,4]})
        return httpx.Response(200,json={'default_generation_settings':{'n_ctx':8192 if failure=='smaller_runtime' else 131072}})
    monkeypatch.setattr(limits.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    p=limits.freeze(providers.LOCAL_QWEN,probe=False)
    if failure:
        with pytest.raises(ValueError,match='核對'):limits.measure(providers.LOCAL_QWEN,'現在去取鎖匙。',p)
    else:
        assert limits.measure(providers.LOCAL_QWEN,'現在去取鎖匙。',p)==4
        assert [r.url.path for r in seen]==['/apply-template','/tokenize','/props']


def test_preflight_preserves_oversized_input_and_writes_failure_receipt(tmp_path):
    p={'kind':'http','context_policy':limits.freeze({'kind':'http','context_window':4096,'max_output_tokens':512})}
    prompt='原文不得改寫。'*1000
    with pytest.raises(ValueError,match='未截斷'):limits.check(p,prompt,{},tmp_path)
    receipt=json.loads((tmp_path/'context-budget.json').read_text())
    assert not receipt['fits'] and receipt['input_tokens']>4096
    assert limits.check({'kind':'http'},prompt,{}) is None  # Legacy jobs stay frozen.


def test_settings_limits_preserve_routing_and_existing_job_budget(client,monkeypatch):
    monkeypatch.setattr(engine.POOL,'submit',lambda *a:None)
    p=client.post('/api/projects',json={'title':'T','idea':'A light goes out.'}).json()
    before=client.get('/api/settings').json()
    assert next(x for x in before['providers'] if x['id']=='local_qwen')['base_url']=='http://127.0.0.1:8080/v1'
    first=client.post('/api/projects/'+p['id']+'/jobs',json={'capability':'narrative'}).json()['job']
    old=first['input']['provider_config']['context_policy']
    r=client.post('/api/settings/context-limits',json={'provider_id':'astra','context_window':65536,'max_output_tokens':8192})
    assert r.status_code==200
    after=client.get('/api/settings').json()
    assert before['routing']==after['routing'] and before['profile']==after['profile']
    assert store.job(first['id'])['input']['provider_config']['context_policy']==old
    assert after['context_profiles']['astra']['context_window']==65536
    assert client.post('/api/settings/context-limits',json={'provider_id':'astra','context_window':4096,'max_output_tokens':4096}).status_code==422
    assert client.post('/api/settings/context-limits',json={'provider_id':'comfy_local','context_window':65536,'max_output_tokens':8192}).status_code==400


def test_http_passes_reserved_output_budget_and_accounts_schema(monkeypatch,tmp_path):
    real=httpx.Client;seen=[]
    def handler(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"text":"done"}'}}]})
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    p={'kind':'http','model':'test','base_url':'http://example.invalid/v1','key_env':'','context_policy':limits.freeze({'kind':'http'})}
    result=providers.http_run(p,'notes','Context',[],tmp_path)
    assert result=={'text':'done'} and seen[0]['max_tokens']==8192
    wire=seen[0]['messages'][0]['content'][0]['text']
    assert json.loads((tmp_path/'context-budget.json').read_text())['input_tokens']==limits.estimate(wire)


def test_only_complete_json_fences_are_unwrapped():
    assert providers.json_content('```json\n{"text":"original"}\n```')=='{"text":"original"}'
    for raw in ('```json\n{"text":"unfinished','explanation\n```json\n{}\n```','```json\n{} trailing\n```'):
        assert providers.json_content(raw)==raw


def test_custom_provider_output_cannot_break_settings(client):
    p={'id':'custom','name':'Custom','kind':'http','base_url':'http://example.invalid/v1','model':'test','capabilities':['narrative'],'max_output_tokens':393216}
    assert client.post('/api/settings/providers',json=p).status_code==400
    assert client.get('/api/settings').status_code==200
    assert client.post('/api/settings/providers',json={**p,'context_window':4096,'max_output_tokens':4000}).status_code==422


def test_historical_budget_receipt_unknown_reasoning_and_allowlist(tmp_path, monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    work=tmp_path/'jobs'/'j';work.mkdir(parents=True)
    assert limits.receipt({'id':'j'}) is None
    (work/'context-budget.json').write_text(json.dumps({'input_tokens':71851,'count_method':'utf8-byte-upper-bound','fits':True}))
    (work/'transport.json').write_text(json.dumps({'finish_reason':'length','content_chars':0,'usage':{'prompt_tokens':True,'completion_tokens':32768,'private':'SECRET'},'reasoning_content':'PRIVATE'}))
    receipt=limits.receipt({'id':'j'})
    assert receipt['input_tokens']==71851 and receipt['fits']
    assert receipt['reasoning_chars'] is None and receipt['content_chars']==0
    assert receipt['usage']['prompt_tokens'] is None
    assert receipt['usage']['completion_tokens']==32768
    assert 'SECRET' not in json.dumps(receipt) and 'PRIVATE' not in json.dumps(receipt)
