"""Human-readable, stable original-image storage; asset IDs remain database identity."""
import hashlib,json,os,re,shutil,unicodedata
from pathlib import Path
from urllib.parse import quote
from . import store


def clean_name(value):
    value=unicodedata.normalize('NFC',str(value))
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]','-',value)
    value=re.sub(r'\s+',' ',value).strip(' .')[:80].rstrip(' .') or 'Untitled'
    if value.upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}: value+='-item'
    return value


def safe_path(relative):
    base=(store.DATA/'assets').resolve();path=store.DATA/relative
    if not path.resolve().is_relative_to(base): raise ValueError('Asset library path escapes storage')
    return path


def layout(pid):
    layouts=store.setting('asset_library_layouts',{})
    if pid not in layouts:
        title=clean_name(store.project(pid)['title']);name=title;number=2
        used={v['folder'].casefold() for v in layouts.values()}
        while name.casefold() in used or (store.DATA/'assets'/name).exists():
            name=f'{title} ({number})';number+=1
        layouts[pid]={'folder':name,'targets':{}}
        store.put_setting('asset_library_layouts',layouts)
    return layouts[pid]


def target_location(pid,target_id,plan=None):
    current=layout(pid)
    if target_id in current['targets']: return current['targets'][target_id]
    plan=plan or store.project(pid)['production'] or {}
    entity=next((e for e in plan.get('canon',[]) if e['id']==target_id),None)
    if entity:
        category={'character':'Characters','crowd':'Crowds','voice':'Voices','location':'Locations','prop':'Props'}[entity['kind']]
        name=clean_name(entity['name']);directory=f'{category}/{name}';n=2
        used={v['directory'].casefold() for v in current['targets'].values()}
        while directory.casefold() in used:
            directory=f'{category}/{name} ({n})';n+=1
        record={'directory':directory,'prefix':name+'-reference','label':entity['name']}
    else:
        found=next(((i,s,f) for i,s in enumerate(plan.get('shots',[]),1) for f in s['keyframes'] if f['id']==target_id),None)
        if found:
            number,shot,frame=found
            scene_number,scene=next((i,s) for i,s in enumerate(plan['scenes'],1) if s['id']==shot['scene_id'])
            directory=f'Scenes/S{scene_number:02d}-{clean_name(scene["title"])}/SH{number:02d}-{clean_name(shot["title"])}'
            record={'directory':directory,'prefix':'Opening' if frame['moment']=='start' else 'Ending' if frame['moment']=='end' else 'Key-'+str(frame['source_time']).replace('.','_'),'label':shot['title']+' · '+(str(frame['source_time'])+'s key' if frame['moment']=='key' else frame['moment'])}
        else:
            record={'directory':'Retired/'+clean_name(target_id),'prefix':'Reference','label':target_id}
    layouts=store.setting('asset_library_layouts',{});layouts[pid]['targets'][target_id]=record
    store.put_setting('asset_library_layouts',layouts)
    return record


def next_path(pid,target_id,plan=None,variant=""):
    record=target_location(pid,target_id,plan);project_folder=layout(pid)['folder']
    prefix=record['prefix']
    if variant in ('four-view-v1','four-view-v2'):prefix=prefix.removesuffix('-reference')+'-four-view'
    directory=Path('assets')/project_folder/record['directory'];version=1
    # Deleted versions remain reserved in the text audit. Reusing their paths
    # would make historical jobs point at a different image.
    with store.db() as c:
        retired={json.loads(r['detail']).get('path') for r in c.execute('SELECT detail FROM events WHERE project_id=? AND kind="asset_deleted"',(pid,))}
    while True:
        relative=directory/f'{prefix}-v{version:03d}.png'
        if str(relative) not in retired and not safe_path(relative).exists(): return relative
        version+=1


def same_references(left,right):
    # File organization can change while the actual approved image stays the same.
    return [{k:v for k,v in r.items() if k!='path'} for r in left]==[{k:v for k,v in r.items() if k!='path'} for r in right]


def write_text(path,text):
    if path.exists() and path.read_text()==text:return
    temporary=path.with_name('.'+path.name+'.tmp');temporary.write_text(text);os.replace(temporary,path)


def write_catalog(pid):
    current=layout(pid);base=safe_path(Path('assets')/current['folder']);base.mkdir(parents=True,exist_ok=True)
    assets=sorted(store.assets(pid),key=lambda a:(a['created'],a['id']))
    records=[];groups={}
    for asset in assets:
        original=safe_path(asset['path'])
        # Legacy assets are organized explicitly, never as a read-side effect.
        if not original.is_relative_to(base):continue
        location=current['targets'].get(asset['target_id'],{'label':asset['target_id']})
        label=location['label'];relative=original.relative_to(base).as_posix()
        record={'name':label,'filename':original.name,'status':asset['status'],'created':asset['created'],'path':relative,'asset_id':asset['id'],'reference_ids':asset['reference_ids'],'review':asset['review'],'note':asset['note']}
        records.append(record);groups.setdefault(original.parent,[]).append(record)
        write_text(original.with_suffix('.json'),json.dumps({**asset,'name':label},ensure_ascii=False,indent=2)+'\n')
        write_text(original.with_name(original.stem+'-prompt.txt'),asset['prompt'])
    intro='# '+store.project(pid)['title']+' — Asset library\n\nOriginal images, organized by character, location, prop and scene/shot. Opening, Ending and time-labelled Key images are single-moment keyframes.\n\n**Use images marked approved.** Higher version numbers do not automatically mean approved. Rejected images are deleted when no longer in use; only their text decision history is retained. Superseded and stale versions remain available. Edit production facts and approvals in Continuity Studio. The library refreshes its version lists and metadata automatically.\n\n'
    def table(items,local=False):
        lines=['| Image | Version file | Status |','|---|---|---|']
        for r in items:
            link=quote(r['filename'] if local else r['path'],safe='/')
            lines.append('| '+r['name'].replace('|','/')+' | ['+r['filename']+']('+link+') | '+r['status']+' |')
        return '\n'.join(lines)+'\n'
    write_text(base/'Asset library.md',intro+table(records))
    write_text(base/'asset-index.json',json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    for directory,items in groups.items():write_text(directory/'Versions.md','# Image versions\n\nUse the row marked **approved**. Other versions remain preserved.\n\n'+table(items,True))
    return base


def migrate_project(pid):
    """Caller must back up and stop generation first. Retain old-path compatibility links."""
    moves=[]
    for asset in sorted(store.assets(pid),key=lambda a:(a['created'],a['id'])):
        old=safe_path(asset['path'])
        project_root=safe_path(Path('assets')/layout(pid)['folder'])
        if old.is_relative_to(project_root):continue
        plan=store.project(pid)['production']
        if asset.get('job_id'):
            try:plan=store.job(asset['job_id'])['input'].get('production') or plan
            except ValueError:pass
        new=safe_path(next_path(pid,asset['target_id'],plan));new.parent.mkdir(parents=True,exist_ok=True)
        before=hashlib.sha256(old.read_bytes()).hexdigest()
        shutil.copy2(old,new)
        if hashlib.sha256(new.read_bytes()).hexdigest()!=before:raise ValueError('Image verification failed')
        new_relative=new.relative_to(store.DATA).as_posix()
        with store.db() as c:c.execute('UPDATE assets SET path=? WHERE id=?',(new_relative,asset['id']))
        # Atomically replace the old pathname with a link, preserving frozen job inputs.
        alias=old.with_name('.'+old.name+'.link');alias.symlink_to(os.path.relpath(new,old.parent));os.replace(alias,old)
        moves.append({'asset_id':asset['id'],'old':asset['path'],'new':new_relative,'sha256':before})
    write_catalog(pid)
    return moves
