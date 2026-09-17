import copy,json
import httpx
import pytest
from PIL import Image
from studio import providers,provider_profiles as profiles,store,engine,models
from test_production import client,plan,create,add_asset


def test_profile_roundtrip_covers_all_capabilities_and_future_skills(client,plan):
    pid=create(client,plan);before=store.project(pid)
    store.put_setting('routing',{'old_skill':'manual','h3':'manual'})
    r=client.post('/api/settings/profile',json={'mode':'deepseek'})
    assert r.status_code==200,r.text
    assert r.json()['mode']=='deepseek'
    for cap in providers.BUILTINS+['old_skill','future_skill']:
        assert providers.resolve(cap)['id']==('manual' if cap=='image' else 'deepseek')
    assert store.project(pid)==before
    client.post('/api/settings/routing',json={'capability':'qc','provider_id':'astra'})
    assert client.get('/api/settings').json()['profile']['mode']=='custom'
    assert client.post('/api/settings/profile',json={'mode':'astra'}).json()['mode']=='astra'
    assert all(providers.resolve(c)['id']=='astra' for c in providers.BUILTINS+['old_skill','future_skill'])
    assert store.project(pid)==before


@pytest.mark.parametrize('patch',[{'mode':'invalid'},{'mode':'deepseek','image_provider':'astra'},{'mode':'deepseek','image_provider':'deepseek'},{'mode':'deepseek','model':'missing-model'},{'mode':'deepseek','key_env':'sk-actual-secret'},{'mode':'deepseek','vision_model':'deepseek-v4-pro'}])
def test_invalid_profile_is_atomic(client,patch):
    before=client.get('/api/settings').json()
    assert client.post('/api/settings/profile',json=patch).status_code in (400,422)
    after=client.get('/api/settings').json()
    assert before['routing']==after['routing'] and before['profile']==after['profile']


def test_account_specific_deepseek_flash_model_is_accepted(client):
    response=client.post('/api/settings/profile',json={'mode':'deepseek','model':'deepseek-flash'})
    assert response.status_code==200,response.text
    assert response.json()['deepseek']['model']=='deepseek-flash'
    assert providers.deepseek_provider()['model']=='deepseek-flash'


def test_direct_api_key_is_saved_locally_and_not_returned(client,monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    response=client.post('/api/settings/profile',json={'mode':'deepseek','model':'deepseek-flash','vision_model':'deepseek-flash','api_key':'test-only-secret'})
    assert response.status_code==200,response.text
    assert response.json()['deepseek']['credential_configured']
    assert 'test-only-secret' not in response.text
    path=store.DATA/'studio-credentials.json'
    assert path.is_file() and (path.stat().st_mode & 0o777)==0o600
    assert profiles.credential_value('DEEPSEEK_API_KEY')=='test-only-secret'


def test_deepseek_protected_and_not_an_image_provider(client):
    assert client.post('/api/settings/routing',json={'capability':'image','provider_id':'deepseek'}).status_code==400
    assert client.post('/api/settings/providers',json={'id':'deepseek','name':'fake','kind':'http','model':'fake','base_url':'http://localhost:1','capabilities':['*']}).status_code==400
    renderer={'id':'external_image','name':'Test-only image renderer','kind':'http','model':'fixture','base_url':'http://localhost:1','capabilities':['image']}
    assert client.post('/api/settings/providers',json=renderer).status_code==200
    assert client.post('/api/settings/profile',json={'mode':'deepseek','image_provider':renderer['id']}).json()['mode']=='deepseek'
    assert providers.resolve('image')['id']==renderer['id']


def mock_client(monkeypatch,reply):
    seen=[];real=httpx.Client
    def handler(request):
        seen.append(request)
        return httpx.Response(200,json=reply)
    monkeypatch.setattr(providers.httpx,'Client',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    return seen


@pytest.mark.parametrize('count',[0,2])
def test_deepseek_text_vision_transport_and_schema(client,monkeypatch,tmp_path,count):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-only-secret')
    seen=mock_client(monkeypatch,{'choices':[{'message':{'content':'{"text":"Production direction"}'},'finish_reason':'stop'}]})
    refs=[]
    for n in range(count):
        p=tmp_path/f'ref{n}.png';Image.new('RGB',(8,8),'red').save(p);refs.append(p)
    result=providers.run(providers.deepseek_provider(),'h3','Return JSON',refs,tmp_path/'job')
    assert result=={'text':'Production direction'}
    payload=json.loads(seen[0].content)
    assert payload['model']=='deepseek-flash'
    assert payload['response_format']=={'type':'json_object'}
    content=payload['messages'][0]['content']
    if count:
        assert len(content)==count+1
        assert all(x['image_url']['url'].startswith('data:image/png;base64,') for x in content[1:])
    else:assert isinstance(content,str) and 'schema' in content
    assert 'test-only-secret' not in json.dumps(client.get('/api/settings').json())


@pytest.mark.parametrize('content,finish',[('', 'stop'),('{"text":"cut short"}','length'),('invalid json','stop'),('{}','stop')])
def test_invalid_output_no_fallback(client,monkeypatch,tmp_path,content,finish):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-key')
    seen=mock_client(monkeypatch,{'choices':[{'message':{'content':content},'finish_reason':finish}]})
    monkeypatch.setattr(providers,'codex_run',lambda *args:pytest.fail('Astra fallback forbidden'))
    with pytest.raises((RuntimeError,ValueError)):
        providers.run(providers.deepseek_provider(),'h3','Direction',[],tmp_path)
    assert len(seen)==1


def test_missing_key_and_image_rejection_before_network(client,monkeypatch,tmp_path):
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.setattr(providers.httpx,'Client',lambda **kw:pytest.fail('Network request forbidden'))
    with pytest.raises(RuntimeError,match='credential'):
        providers.run(providers.deepseek_provider(),'h3','Direction',[],tmp_path)
    with pytest.raises(ValueError,match='does not generate'):
        providers.run(providers.deepseek_provider(),'image','Direction',[],tmp_path)
    result=client.post('/api/settings/deepseek/check',json={}).json()
    assert not result['ok'] and 'DEEPSEEK_API_KEY' in result['message']


def test_connection_only_lists_models(client,monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-key')
    seen=mock_client(monkeypatch,{'data':[{'id':'deepseek-flash'},{'id':'deepseek-v4-pro'}]})
    assert profiles.check_connection()['ok']
    assert len(seen)==1 and seen[0].method=='GET' and seen[0].url.path=='/models'


def test_jobs_freeze_provider_and_do_not_change_canon(client,plan,monkeypatch):
    pid=create(client,plan);before=copy.deepcopy(store.project(pid));scheduled=[]
    monkeypatch.setattr(engine.POOL,'submit',lambda *args:scheduled.append(args))
    profiles.apply('deepseek')
    first=engine.enqueue(pid,models.JobRequest(capability='qc'))['job']
    assert first['provider']=='deepseek' and first['input']['provider_config']['vision_model']=='deepseek-flash'
    assert 'You are Astra' not in first['input']['prompt']
    frozen=copy.deepcopy(first)
    profiles.apply('astra')
    assert store.job(first['id'])==frozen
    second=engine.enqueue(pid,models.JobRequest(capability='qc'))['job']
    assert second['provider']=='astra' and len(scheduled)==2
    assert store.project(pid)==before
