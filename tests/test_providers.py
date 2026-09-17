from pathlib import Path
import json,threading,base64,io
from http.server import BaseHTTPRequestHandler,HTTPServer
from PIL import Image
import pytest
from studio import providers,models,h3

@pytest.fixture
def endpoint():
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=self.rfile.read(int(self.headers['Content-Length']));seen.append((self.path,self.headers,body))
            if self.path.endswith('/chat/completions'):
                response={'choices':[{'message':{'content':json.dumps({'text':'Externally produced performance notes'})}}]}
            else:
                buf=io.BytesIO();Image.new('RGB',(256,256),'blue').save(buf,format='PNG')
                response={'data':[{'b64_json':base64.b64encode(buf.getvalue()).decode()}]}
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(response).encode())
    server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield {'kind':'http','base_url':f'http://127.0.0.1:{server.server_port}/v1','model':'test-only-contract-provider','key_env':''},seen
    server.shutdown();thread.join();server.server_close()

def test_http_text_and_actual_image_bytes(endpoint,tmp_path):
    provider,seen=endpoint
    result=providers.http_run(provider,'performance_notes','A short production',[],tmp_path)
    assert result['text']=='Externally produced performance notes'
    first=providers.http_run(provider,'image','A visual target',[],tmp_path)
    with Image.open(first['image_path']) as im:assert im.size==(256,256)
    ref=tmp_path/'ref.png';Image.new('RGB',(256,256),'red').save(ref)
    providers.http_run(provider,'image','Preserve this reference',[ref],tmp_path)
    assert [x[0] for x in seen]==['/v1/chat/completions','/v1/images/generations','/v1/images/edits']
    assert b'name="image[]"' in seen[-1][2] and b'Preserve this reference' in seen[-1][2]

def test_missing_configured_secret_fails_without_request(endpoint,tmp_path):
    provider,seen=endpoint;provider['key_env']='STUDIO_NONEXISTENT_TEST_KEY'
    with pytest.raises(RuntimeError,match='credential'):providers.http_run(provider,'qc','Review',[],tmp_path)
    assert not seen

def test_h3_validator_rejects_changed_dialogue_and_refs():
    compiled={'text':'anchor\n\nintegrated_multimodal_description: x','references':[{}]};shot={'dialogue':[{'text':'Stay here.'}]}
    good='anchor\n\nintegrated_multimodal_description: <Picture 1> <d>[English] Stay here.</d>\n\noverall_soundscape: Wind.\n\nnon_diegetic_music: N/A'
    assert h3.validate_refinement(good,compiled,shot)==good
    for bad in [good.replace('Stay here.','Go away.'),good.replace('Picture 1','Picture 7'),good.replace('anchor','changed'),good.replace('overall_soundscape:','noise:')]:
        with pytest.raises(ValueError):h3.validate_refinement(bad,compiled,shot)


@pytest.mark.parametrize('count',[0,1,5,6,7])
def test_codex_freezes_and_passes_all_reference_images(monkeypatch,tmp_path,count):
    refs=[]
    for i in range(count):
        p=tmp_path/f'input-{i}.png';Image.new('RGB',(32,32),(i*30,0,0)).save(p);refs.append(p)
    work=tmp_path/'job with spaces';seen={}
    monkeypatch.setattr(providers.shutil,'which',lambda name:'/test/codex')
    class Process:
        returncode=0
        def __init__(self,cmd,**kwargs):
            seen['cmd']=cmd
            seen['prompt']=kwargs['stdin'].read().decode()
        def communicate(self,timeout):
            (work/'result.json').write_text(json.dumps({'image_path':str(work/'test-output.png'),'notes':'test-only subprocess contract'}))
    monkeypatch.setattr(providers.subprocess,'Popen',Process)
    providers.codex_run(providers.DEFAULT,'image','Keep all identities.',refs,work)
    attached=[seen['cmd'][i+1] for i,v in enumerate(seen['cmd']) if v=='-i']
    assert len(attached)==min(count,5)
    for i,(src,dst) in enumerate(zip(refs,attached if count<=5 else attached[:4]),1):
        assert Path(dst).name==f'reference-{i}.png'
        assert Path(dst).read_bytes()==src.read_bytes()
        assert Path(dst).parent==work
    if count>5:
        transport=json.loads((work/'reference-transport.json').read_text())
        assert len(transport['inputs'])==5
        assert [t['image_number'] for t in transport['tiles']]==list(range(5,count+1))
        with Image.open(transport['board']) as board:
            for tile in transport['tiles']:
                with Image.open(tile['source']) as src:assert board.crop(tile['box']).tobytes()==src.convert('RGB').tobytes()
        assert attached==transport['inputs']
        assert 'num_last_images_to_include=5' in seen['prompt']
        assert 'Do not supply referenced_image_paths' in seen['prompt']
        assert 'num_last_images_to_include='+str(count) not in seen['prompt']
    elif count:
        assert 'num_last_images_to_include='+str(count) in seen['prompt']
    else:assert 'num_last_images_to_include' not in seen['prompt']
