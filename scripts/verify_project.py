#!/usr/bin/env python3
"""Read-only live acceptance verifier. Does not generate or approve anything."""
import argparse,urllib.request,json,io,zipfile,hashlib,re
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('project_id');p.add_argument('--base',default='http://127.0.0.1:4760');p.add_argument('--output');args=p.parse_args()
base=args.base+'/api'
def get(path):return urllib.request.urlopen(base+path,timeout=30).read()
s=json.loads(get('/projects/'+args.project_id));plan=s['production'];assert plan
approved={a['target_id']:a for a in s['assets'] if a['status']=='approved'}
assert len([e for e in plan['canon'] if e['kind']=='character'])>=2
assert any(e['kind']=='location' for e in plan['canon']) and len(plan['shots'])>=3
for e in plan['canon']:assert e['id'] in approved, 'Missing approved identity '+e['id']
reference_sets=[];image_hashes=[]
for shot in plan['shots']:
    frames=shot['keyframes']
    assert all(f['id'] in approved for f in frames),'Missing planned approved frame '+shot['id']
    scene=next(s for s in plan['scenes'] if s['id']==shot['scene_id'])
    expected_refs={approved[e]['id'] for e in set(shot['entity_ids'])|{scene['location_id']}}
    for f in frames:
        a=approved[f['id']];assert a['reference_ids'],'Missing reference provenance'
        assert expected_refs<=set(a['reference_ids']),'Missing current canonical reference '+f['id']
        reference_sets.append(set(a['reference_ids']))
        imdata=get('/assets/'+a['id']+'/image');image_hashes.append(hashlib.sha256(imdata).hexdigest())
        with Image.open(io.BytesIO(imdata)) as im:assert im.width>=256 and im.height>=256
        assert a['review'],'No actual visual review'
        assert a['review']['verdict']=='pass' or a['note'].strip(),'Unexplained review override'
assert set.intersection(*reference_sets),'Frames did not reuse approved identity references'
assert len(set(image_hashes))==len(image_hashes),'Distinct keyframes should not reuse identical pixels'
delivery=s['delivery'];assert delivery['mode']=='REF2VA'
fields=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
chapters={c['shot_id']:c for scene in delivery['scenes'] for c in scene['chapters']}
assert set(chapters)=={shot['id'] for shot in plan['shots']}
for scene in delivery['scenes']:
    for c in scene['chapters']:
        assert not c['issues'], c['issues']
        assert c['references'][:len(scene['references'])]==scene['references']
        assert c['text']==scene['global_prompt']+'\n\n'+c['shot_prompt']
        assert all(c['text'].count(field+':')==1 for field in fields)
        assert [c['text'].index(f+':') for f in fields]==sorted(c['text'].index(f+':') for f in fields)
        assert set(re.findall(r'<Picture\s+(\d+)>',c['text']))<={r['label'].split()[-1] for r in c['references']}
        assert re.search(r'summary:\s*\[reference generation\]',c['text'])
        assert len(c['text'])<=7000
for i,shot in enumerate(plan['shots']):
    c=chapters[shot['id']];assert c['duration']==shot['duration']
    assert c['guidance']['previous_shot_id']==(plan['shots'][i-1]['id'] if i else None)
    for dialogue in shot['dialogue']:assert dialogue['text'] in c['shot_prompt']
package=get('/projects/'+args.project_id+'/export')
with zipfile.ZipFile(io.BytesIO(package)) as z:
    handoff=json.loads(z.read('ref2/handoff.json'))
    assert handoff['chapter_order']==[shot['id'] for shot in plan['shots']]
    for scene in delivery['scenes']:
        folder='ref2/scenes/'+scene['scene_id']
        assert z.read(folder+'/global.txt').decode()==scene['global_prompt']
        for c in scene['chapters']:
            path=folder+'/chapters/'+c['shot_id']
            for filename,key in [('shot','shot_prompt'),('complete','text')]:
                assert z.read(path+'/'+filename+'.txt').decode()==c[key]
            assert json.loads(z.read(path+'/references-and-guidance.json'))['guidance']==c['guidance']
            assert all(r['path'] in z.namelist() for r in c['references'])
    for shot in plan['shots']:
        h=json.loads(z.read('h3/'+shot['id']+'.json'))
        assert h['mode']!='T2VA','Expected actual approved frame anchors'
        for ref in h['references']:assert ref['path'] in z.namelist()
        text=z.read('h3/'+shot['id']+'.txt').decode()
        for field in ['integrated_multimodal_description:','overall_soundscape:','non_diegetic_music:']:assert field in text
        for d in shot['dialogue']:assert d['text'] in text
assert not [q for q in s['qc'] if q['level']=='error']
report={'project_id':s['id'],'title':s['title'],'revision':s['revision'],'shots':len(plan['shots']),'approved_assets':len(approved),'distinct_frame_images':len(image_hashes),'h3_modes':{h['shot_id']:h['mode'] for h in s['h3']},'default_mode':delivery['mode'],'scene_globals':len(delivery['scenes']),'ref2_chapters':len(chapters),'continuity_enabled':delivery['configuration']['continuity_enabled'],'character_sheets':{c['name']:c['status'] for c in s.get('character_sheets',{}).get('characters',[])},'archive_bytes':len(package),'result':'PASS'}
if args.output:
    from pathlib import Path
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);(out/'acceptance.json').write_text(json.dumps(report,indent=2));(out/'production-package.zip').write_bytes(package);(out/'project-state.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
print(json.dumps(report,indent=2))
