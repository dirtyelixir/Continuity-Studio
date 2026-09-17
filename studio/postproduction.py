"""Versioned character voices and dialogue takes, independent of visual canon."""
import hashlib, io, json, threading, wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import Field
from . import store, models, engine

router=APIRouter()
POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='studio-voice')
MAX_UPLOAD=20*1024*1024
AUDITION_TEXTS={
    '英文':"Hello, I'm here. Let's tell this story together.",
    '粵語（香港）':'你好，我喺度。等我哋一齊將呢個故事講落去。',
    '國語（台灣）':'你好，我在這裡。讓我們一起把這個故事說下去。',
    '中文（大陸）':'你好，我在这里。让我们一起把这个故事说下去。',
}
LANGUAGE_ALIASES={'en':'英文','english':'英文','yue':'粵語（香港）','yue-hk':'粵語（香港）','cantonese':'粵語（香港）','zh-tw':'國語（台灣）','zh-cn':'中文（大陸）','zh':'中文（大陸）','mandarin':'中文（大陸）'}


def default_audition(language):
    return AUDITION_TEXTS.get(LANGUAGE_ALIASES.get(language.lower(),language))


def character_language(pid,cid):
    plan=store.project(pid).get('production') or {}
    dialogue=[d for s in plan.get('shots',[]) for d in s.get('dialogue',[]) if not silent_dialogue(d)]
    own=[d for d in dialogue if d['entity_id']==cid]
    languages={LANGUAGE_ALIASES.get(d['language'].lower(),d['language']) for d in (own or dialogue)}
    return next(iter(languages)) if len(languages)==1 and next(iter(languages)) in AUDITION_TEXTS else '粵語（香港）'

class VoiceEdit(models.Strict):
    version:int=Field(ge=0)
    description:str=Field(min_length=1,max_length=1200)
    language:str=Field(default="",max_length=100)
    sample_text:str=Field(default="",max_length=600)
    sound_mode:Literal["speech","nonverbal"]="speech"
    seed:int=Field(default=42,ge=0,le=2147483647)
    reference_take_id:str|None=Field(default=None,max_length=100)
    reference_mode:Literal['timbre','clone']='timbre'
    reference_text:str=Field(default='',max_length=2000)

class Version(models.Strict):
    version:int=Field(ge=0)

class LineRequest(models.Strict):
    shot_id:str
    dialogue_index:int=Field(ge=0)


def init():
    with store.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS voice_profiles(project_id TEXT NOT NULL REFERENCES projects(id),character_id TEXT NOT NULL,version INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(project_id,character_id));
        CREATE TABLE IF NOT EXISTS voice_takes(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),character_id TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,request TEXT NOT NULL,result TEXT,error TEXT NOT NULL DEFAULT '',created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS voice_lines(project_id TEXT NOT NULL REFERENCES projects(id),line_key TEXT NOT NULL,take_id TEXT NOT NULL REFERENCES voice_takes(id),PRIMARY KEY(project_id,line_key));
        ''')
        c.execute("UPDATE voice_takes SET state='interrupted',error='工作台重啟，請檢查已保存音檔後再重新生成。',updated=? WHERE state IN ('queued','running','importing')",(store.now(),))


def character(pid,cid):
    p=store.project(pid)
    ent=next((e for e in (p['production'] or {}).get('canon',[]) if e['id']==cid and e['kind'] in ('character','crowd','voice')),None)
    if not ent: raise ValueError('找不到本作品的角色；請先採用製作方案。')
    return ent


def profile(pid,cid):
    with store.db() as c:r=c.execute('SELECT * FROM voice_profiles WHERE project_id=? AND character_id=?',(pid,cid)).fetchone()
    if r:return {'character_id':cid,'version':r['version'],**json.loads(r['payload'])}
    language=character_language(pid,cid)
    from . import voice_defaults
    default=voice_defaults.cached(store.project(pid),cid)
    return {'character_id':cid,'version':0,'description':'','language':language,'sample_text':default_audition(language),'seed':42,'selected_take_id':None,**({'default_voice':default} if default else {})}



class DefaultRequest(Version):
    retry:bool=False


@router.get('/api/projects/{pid}/voices/{cid}/default')
def read_default(pid:str,cid:str):
    character(pid,cid)
    return {'profile':profile(pid,cid)}


@router.post('/api/projects/{pid}/voices/{cid}/default')
def prepare_default(pid:str,cid:str,data:DefaultRequest):
    from . import voice_defaults
    with engine.LOCK:
        character(pid,cid);v=profile(pid,cid)
        if v['version']!=data.version:raise ValueError('音色已被更新，請重新載入。')
        if v['description'] or v.get('default_voice'):return {'profile':v}
        job=voice_defaults.latest(store.project(pid),cid)
        if job and (not data.retry or job['state'] in ('queued','running','awaiting_input')):
            return {'profile':v,'job':job}
        return {'profile':v,**engine.enqueue(pid,models.JobRequest(capability='voice_defaults',target_id=cid))}


def config(p):
    result={k:p[k] for k in ('description','language','sample_text','seed')}
    if p.get('sound_mode')=='nonverbal':result['sound_mode']='nonverbal'
    # Preserve hashes of every legacy profile and take with no attachment.
    if p.get('reference_take_id'):
        result.update(reference_take_id=p['reference_take_id'],reference_mode=p.get('reference_mode','timbre'),reference_text=p.get('reference_text',''))
    return result


def voice_reference(pid,cid,p):
    if not p.get('reference_take_id'):return None
    ref=take(pid,p['reference_take_id'])
    if ref['character_id']!=cid or ref['state']!='succeeded' or ref['request'].get('provider')!='uploaded' or ref['kind'] not in ('voice','reference'):
        raise ValueError('請選擇本角色已上傳完成的參考聲音。')
    audio_path(ref)
    mode=p.get('reference_mode','timbre');transcript=p.get('reference_text','').strip()
    if p.get('sound_mode')=='nonverbal' and mode=='clone':raise ValueError('非語言聲音不使用人聲 Clone；請以附件作音效參考。')
    if mode=='clone' and not transcript:raise ValueError('Clone 模式需要參考音訊的完整逐字稿。')
    return {'take_id':ref['id'],'sha256':ref['result']['sha256'],'mode':mode,'text':transcript}


def decode(r):
    d=dict(r);d['request']=json.loads(d['request']);d['result']=json.loads(d['result']) if d['result'] else None
    return d


def take(pid,tid):
    with store.db() as c:r=c.execute('SELECT * FROM voice_takes WHERE project_id=? AND id=?',(pid,tid)).fetchone()
    if not r:raise ValueError('找不到本作品的音檔。')
    return decode(r)


def audio_path(t,verify=True):
    if not t['result']:raise ValueError('音檔尚未完成。')
    rel=Path(t['result']['path']);path=store.DATA/rel
    if rel.is_absolute() or '..' in rel.parts or not path.resolve().is_relative_to((store.DATA/'audio').resolve()):raise ValueError('音檔路徑無效。')
    if any(x.is_symlink() for x in [path,*path.parents] if x!=store.DATA.parent):raise ValueError('音檔不能使用符號連結。')
    if not path.is_file():raise ValueError('找不到原始音檔。')
    if verify and hashlib.sha256(path.read_bytes()).hexdigest()!=t['result']['sha256']:raise ValueError('原始音檔已被更改，請重新匯入。')
    return path


def silent_dialogue(d):
    return d.get('delivery','').strip().lower() in {'無聲','只有口形，無聲','silent','inaudible','mouths silently'}


def line_source(pid,sid,index):
    p=store.project(pid)
    shot=next((s for s in (p['production'] or {}).get('shots',[]) if s['id']==sid),None)
    if not shot or index>=len(shot['dialogue']):raise ValueError('找不到這句分鏡對白。')
    d=shot['dialogue'][index]
    if silent_dialogue(d):raise ValueError('這句分鏡明確標示為無聲口形，不會生成配音。若要發聲，請先修改分鏡的表演設定。')
    character(pid,d['entity_id'])
    v=profile(pid,d['entity_id'])
    if v.get('sound_mode')=='nonverbal':raise ValueError('此角色使用非語言聲音，不生成對白人聲；請在剪接中安排已匯入的角色音效。')
    if not v['selected_take_id']:raise ValueError('請先為說話角色採用一個音色。')
    ref=take(pid,v['selected_take_id'])
    if ref['request']['config_hash']!=store.digest(config(v)):raise ValueError('音色設定已更新，請先試聽並採用新版音色。')
    audio_path(ref)
    source={'shot_id':sid,'dialogue_index':index,'dialogue':d,'shot_duration':shot['duration'],'voice_take_id':ref['id'],'voice_sha256':ref['result']['sha256'],'config_hash':store.digest(config(v))}
    if ref['request'].get('voice_reference',{}).get('mode')=='clone':
        source.update(reference_mode='clone',reference_text=ref['request']['text'])
    return source


def current(pid,t):
    try:
        character(pid,t['character_id'])
        if t['kind']=='reference':
            audio_path(t);return True
        if t['kind']=='voice':
            if t['request'].get('voice_reference'):
                if t['request']['voice_reference']!=voice_reference(pid,t['character_id'],profile(pid,t['character_id'])):return False
            return t['request']['config_hash']==store.digest(config(profile(pid,t['character_id'])))
        r=t['request'];return r['source']==line_source(pid,r['source']['shot_id'],r['source']['dialogue_index'])
    except (ValueError,KeyError):return False


@router.put('/api/projects/{pid}/voices/{cid}')
def save_profile(pid:str,cid:str,data:VoiceEdit):
    with engine.LOCK,store.db() as c:
        character(pid,cid);old=profile(pid,cid)
        if old['version']!=data.version:raise ValueError('音色已被更新，請重新載入後再儲存。')
        payload={k:v.strip() if isinstance(v,str) else v for k,v in data.model_dump(exclude={'version'}).items()}
        if 'sound_mode' not in data.model_fields_set:payload['sound_mode']=old.get('sound_mode','speech')
        if payload['sound_mode']=='nonverbal':
            payload['language']='';payload['sample_text']=''
        else:payload.pop('sound_mode')
        if payload['sample_text'] in AUDITION_TEXTS.values() and default_audition(payload['language']):
            payload['sample_text']=default_audition(payload['language'])
        # Old clients omit attachment fields: preserve an existing attachment.
        if 'reference_take_id' not in data.model_fields_set:
            payload.update({k:old[k] for k in ('reference_take_id','reference_mode','reference_text') if k in old})
        if not payload.get('reference_take_id'):
            for key in ('reference_take_id','reference_mode','reference_text'):payload.pop(key,None)
        voice_reference(pid,cid,payload)
        if not payload['description']:raise ValueError('請填寫角色聲音描述。')
        if payload.get('sound_mode')!='nonverbal' and any(not payload[k] for k in ['language','sample_text']):raise ValueError('請填寫音色描述、語言及試音對白。')
        payload['selected_take_id']=old['selected_take_id'] if config(old)==config(payload) else None
        c.execute('INSERT OR REPLACE INTO voice_profiles VALUES(?,?,?,?)',(pid,cid,old['version']+1,store.encode(payload)))
        store.event(c,pid,'voice_profile',character(pid,cid)['name']+'：更新音色設定')
    return profile(pid,cid)


def insert_take(pid,cid,kind,request,state='queued',result=None):
    tid=store.uid();stamp=store.now()
    with store.db() as c:
        c.execute('INSERT INTO voice_takes VALUES(?,?,?,?,?,?,?,?,?,?)',(tid,pid,cid,kind,state,store.encode(request),store.encode(result) if result else None,'',stamp,stamp))
    return take(pid,tid)


def enqueue(pid,cid,kind,request):
    with store.db() as c:
        rows=c.execute("SELECT * FROM voice_takes WHERE project_id=? AND state IN ('queued','running')",(pid,)).fetchall()
    for row in rows:
        existing=decode(row)
        if existing['kind']==kind and existing['character_id']==cid and existing['request']==request:return existing
    t=insert_take(pid,cid,kind,request)
    POOL.submit(run,t['id'],pid)
    return t


@router.post('/api/projects/{pid}/voices/{cid}/generate')
def design_voice(pid:str,cid:str,data:Version):
    with engine.LOCK:
        character(pid,cid);p=profile(pid,cid)
        if p['version']!=data.version:raise ValueError('音色設定已更新，請重新載入。')
        if p.get('sound_mode')=='nonverbal':raise ValueError('非語言聲音不使用 VoxCPM 人聲生成；請匯入角色音效並試聽採用。')
        if not p['description']:raise ValueError('請先儲存角色音色描述。')
        with store.db() as c:
            previous=[decode(r) for r in c.execute("SELECT * FROM voice_takes WHERE project_id=? AND character_id=? AND kind='voice'",(pid,cid))]
        same=[t for t in previous if t['request'].get('config_hash')==store.digest(config(p)) and t['request'].get('provider')=='voxcpm2']
        pending=next((t for t in same if t['state'] in ['queued','running']),None)
        if pending:return pending
        seed=(p['seed']+len(same))%2147483648
        reference=voice_reference(pid,cid,p)
        request={'provider':'voxcpm2','text':p['sample_text'],'control':p['description']+'；'+p['language'],'seed':seed,'config':config(p),'config_hash':store.digest(config(p))}
        if reference:
            request['voice_reference']=reference
            # Clone follows reference expression; a conflicting text-designed voice
            # must not replace the reference identity or performance.
            if reference['mode']=='clone':request['control']=''
        return enqueue(pid,cid,'voice',request)


@router.post('/api/projects/{pid}/voice-lines/generate')
def generate_line(pid:str,data:LineRequest):
    with engine.LOCK:
        source=line_source(pid,data.shot_id,data.dialogue_index);d=source['dialogue'];p=profile(pid,d['entity_id'])
        return enqueue(pid,d['entity_id'],'line',{'provider':'voxcpm2','text':d['text'],'control':'' if source.get('reference_mode')=='clone' else d['language']+'；'+d['delivery'],'seed':p['seed'],'source':source})


def run(tid,pid):
    from . import voxcpm_provider
    t=take(pid,tid)
    folder=store.DATA/'audio'/pid/t['character_id'];folder.mkdir(parents=True,exist_ok=True)
    output=folder/(tid+'.wav');work=folder/(tid+'-job')
    try:
        with store.db() as c:c.execute("UPDATE voice_takes SET state='running',updated=? WHERE id=?",(store.now(),tid))
        request=dict(t['request'])
        if t['kind']=='line':
            ref=take(pid,request['source']['voice_take_id']);request['reference_path']=str(audio_path(ref))
            if request['source'].get('reference_mode')=='clone':
                request.update(reference_mode='clone',reference_text=request['source']['reference_text'])
        elif request.get('voice_reference'):
            source=request['voice_reference'];ref=take(pid,source['take_id'])
            if ref['character_id']!=t['character_id'] or ref['result']['sha256']!=source['sha256']:raise ValueError('參考聲音來源不符。')
            request.update(reference_path=str(audio_path(ref)),reference_mode=source['mode'],reference_text=source['text'])
        result=voxcpm_provider.synthesize(request,output,work)
        result['path']=str(output.relative_to(store.DATA))
        if t['kind']=='line':
            d=request['source']['dialogue'];result['window_duration']=d['end']-d['start'];result['overrun']=result['duration']>result['window_duration']+0.05
        with store.db() as c:
            c.execute("UPDATE voice_takes SET state='succeeded',result=?,updated=? WHERE id=?",(store.encode(result),store.now(),tid))
            store.event(c,pid,'voice_generated',f'{t["character_id"]}：VoxCPM2 {t["kind"]} {tid}')
    except Exception as e:
        with store.db() as c:c.execute("UPDATE voice_takes SET state='failed',error=?,updated=? WHERE id=?",(str(e)[:2500],store.now(),tid))


@router.post('/api/projects/{pid}/voice-takes/{tid}/adopt')
def adopt(pid:str,tid:str,data:Version):
    with engine.LOCK,store.db() as c:
        t=take(pid,tid)
        if t['kind']=='reference':raise ValueError('這是參考附件；人聲請先生成候選，非語言聲音請使用「匯入角色音效」，再試聽採用。')
        if t['state']!='succeeded' or not current(pid,t):raise ValueError('這個版本尚未完成或來源已更新；請生成新版。')
        audio_path(t)
        p=profile(pid,t['character_id'])
        if data.version!=p['version']:raise ValueError('角色音色已更新，請重新載入。')
        if t['kind']=='voice':
            p['selected_take_id']=tid
            c.execute('UPDATE voice_profiles SET version=?,payload=? WHERE project_id=? AND character_id=?',(p['version']+1,store.encode({k:v for k,v in p.items() if k not in ['version','character_id']}),pid,t['character_id']))
        else:
            r=t['request']['source'];key=f'{r["shot_id"]}:{r["dialogue_index"]}'
            c.execute('INSERT OR REPLACE INTO voice_lines VALUES(?,?,?)',(pid,key,tid))
        store.event(c,pid,'voice_adopted',tid)
    return take(pid,tid)


def inspect_wav(content,min_duration=2):
    try:
        with wave.open(io.BytesIO(content),'rb') as w:
            rate=w.getframerate();frames=w.getnframes();channels=w.getnchannels();width=w.getsampwidth();raw=w.readframes(frames)
            duration=frames/rate
            if channels not in [1,2] or width!=2 or not 8000<=rate<=96000 or not min_duration<=duration<=30 or len(raw)!=frames*channels*width:raise ValueError()
            import array
            samples=array.array('h',raw)
            if max(abs(x) for x in samples)<20:raise ValueError()
        return {'sample_rate':rate,'duration':duration,'sha256':hashlib.sha256(content).hexdigest(),'model':'uploaded-reference'}
    except Exception:raise ValueError(f'請上傳 {min_duration:g}–30 秒、16-bit PCM WAV、單聲道或立體聲的音訊（上限 20 MB）。') from None


@router.post('/api/projects/{pid}/voices/{cid}/upload')
async def upload_voice(pid:str,cid:str,version:int=Form(...),file:UploadFile=File(...),attachment:bool=Form(False),reference_sound_mode:Literal["speech","nonverbal"]|None=Form(None)):
    try:content=await file.read(MAX_UPLOAD+1)
    finally:await file.close()
    if len(content)>MAX_UPLOAD:raise ValueError('音檔上限為 20 MB。')
    with engine.LOCK:
        character(pid,cid);p=profile(pid,cid)
        if version!=p['version'] or (not attachment and not p['description']):raise ValueError('請先儲存目前的音色設定。')
        mode=reference_sound_mode if attachment and reference_sound_mode else p.get('sound_mode','speech')
        metadata=inspect_wav(content,0.1 if mode=='nonverbal' else 2)
        request={'provider':'uploaded','config':config(p),'config_hash':store.digest(config(p)),'filename':(file.filename or 'reference.wav').replace('\\','/').split('/')[-1]}
        t=insert_take(pid,cid,'reference' if attachment else 'voice',request,state='importing')
        path=store.DATA/'audio'/pid/cid/(t['id']+'.wav');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        metadata['path']=str(path.relative_to(store.DATA))
        with store.db() as c:c.execute("UPDATE voice_takes SET state='succeeded',result=? WHERE id=?",(store.encode(metadata),t['id']))
    return take(pid,t['id'])


@router.get('/api/projects/{pid}/voice-takes/{tid}/audio')
def audio_file(pid:str,tid:str):
    t=take(pid,tid);return FileResponse(audio_path(t),media_type='audio/wav',filename=f'{t["character_id"]}-{tid}.wav',content_disposition_type='inline')


@router.post('/api/projects/{pid}/voice-takes/{tid}/reveal')
def reveal(pid:str,tid:str):
    from .folders import reveal_file
    return reveal_file(audio_path(take(pid,tid)))


@router.get('/api/voxcpm/status')
def provider_status():
    from . import voxcpm_provider
    return voxcpm_provider.status()


def state(p):
    pid=p['id'];chars=[e for e in (p['production'] or {}).get('canon',[]) if e['kind'] in ('character','crowd','voice')]
    with store.db() as c:
        takes=[decode(r) for r in c.execute('SELECT * FROM voice_takes WHERE project_id=? ORDER BY created DESC',(pid,))]
        selected={r['line_key']:r['take_id'] for r in c.execute('SELECT * FROM voice_lines WHERE project_id=?',(pid,))}
    profiles=[profile(pid,e['id']) for e in chars]
    for t in takes:
        t['current']=current(pid,t)
        t['selected']=any(v['selected_take_id']==t['id'] for v in profiles) if t['kind']=='voice' else t['id'] in selected.values()
        t['audio_url']=f'/api/projects/{pid}/voice-takes/{t["id"]}/audio' if t['result'] else None
    return {'profiles':profiles,'takes':takes,'selected_lines':selected,'silent_lines':[f'{s["id"]}:{i}' for s in (p['production'] or {}).get('shots',[]) for i,d in enumerate(s['dialogue']) if silent_dialogue(d)],'provider':'VoxCPM2','reference_modes':['timbre','clone'],'sound_modes':['speech','nonverbal']}


def add_export(z,p):
    data=p['postproduction'];z.writestr('postproduction/voices.json',store.encode(data))
    z.writestr('postproduction/README.txt','角色音色與逐句配音。僅採用且來源仍有效的音檔列入交付；其他版本資料保留於 voices.json。對白起止時間以分鏡內的秒數計。音檔未自動裁切、拉伸或混入影片；overrun=true 表示超出原定對白時段，須在剪接中處理。\n')
    for t in data['takes']:
        if t['state']=='succeeded' and t['current'] and t['selected']:
            path=audio_path(t);name=f'postproduction/{t["kind"]}/{t["character_id"]}-{t["id"]}.wav'
            z.write(path,name)
            z.writestr(name+'.json',store.encode(t))
    reference_ids={v['reference_take_id'] for v in data['profiles'] if v.get('reference_take_id')}
    reference_ids.update(t['request']['voice_reference']['take_id'] for t in data['takes'] if t['selected'] and t['current'] and t['request'].get('voice_reference'))
    for tid in sorted(reference_ids):
        ref=take(p['id'],tid);path=audio_path(ref)
        name=f'postproduction/reference/{ref["character_id"]}-{tid}.wav'
        z.write(path,name);z.writestr(name+'.json',store.encode(ref))
