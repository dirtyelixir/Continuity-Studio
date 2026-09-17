import copy,io,json,zipfile
import pytest
from studio import delivery,store,engine,models,prompt_preparation
from test_production import client,plan,create,add_asset
from test_prompt_preparation import result_for,save_result


def setup_props(client,plan,approved=True):
    for eid,name in [('jug','Water jug'),('driver','Screwdriver')]:
        plan['canon'].append({'id':eid,'kind':'prop','name':name,'description':'Distinct blue plastic design.','facts':[]})
    second=copy.deepcopy(plan['shots'][0]);second.update(id='shot2',keyframes=[{'id':'frame2','moment':'start','description':'Second shot'}])
    plan['shots'].append(second)
    plan['shots'][0]['entity_ids'].append('jug')
    plan['shots'][1]['entity_ids'].append('driver')
    pid=create(client,plan)
    for eid in ['ada','room']+(['jug','driver'] if approved else []):add_asset(pid,plan,eid)
    result=result_for(plan)
    result['subjects'] += [{'entity_id':eid,'name_en':name,'appearance':'Distinct blue plastic design.'} for eid,name in [('jug','Water jug'),('driver','Screwdriver')]]
    second=copy.deepcopy(result['shots'][0]);second['shot_id']='shot2';result['shots'].append(second)
    for item,eid in zip(result['shots'],['jug','driver']):item['shot_prompt']=item['shot_prompt'].replace('presses the switch.',f'holds <Entity {eid}>.')
    save_result(pid,result,prompt_preparation.source(plan,'scene'))
    return pid


def test_local_props_resolve_per_shot_and_export_with_no_global_inventory(client,plan):
    pid=setup_props(client,plan);before=store.project(pid);jobs=store.jobs(pid);assets=store.assets(pid)
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert [r['target_id'] for r in scene['references']]==['ada','room']
    assert 'Water jug' not in scene['global_prompt'] and 'Screwdriver' not in scene['global_prompt']
    for chapter,eid,name in zip(scene['chapters'],['jug','driver'],['Water jug','Screwdriver']):
        assert [r['target_id'] for r in chapter['local_references']]==[eid]
        assert chapter['local_references'][0]['label']=='Picture 3'
        assert [r['target_id'] for r in chapter['references']]==['ada','room',eid]
        assert f'<Subject 3> is {name} from <Picture 3>' in chapter['shot_prompt']
        assert 'holds <Subject 3>' in chapter['shot_prompt']
        assert chapter['shot_prompt'].index('<Picture 3>')<chapter['shot_prompt'].index('summary:')
        assert chapter['text']==scene['global_prompt']+'\n\n'+chapter['shot_prompt'] and not chapter['issues']
    assert 'Screwdriver' not in scene['chapters'][0]['text']
    assert 'Water jug' not in scene['chapters'][1]['text']
    with zipfile.ZipFile(io.BytesIO(client.get('/api/projects/'+pid+'/export').content)) as z:
        assert z.read('ref2/scenes/scene/global.txt').decode()==scene['global_prompt']
        for chapter in scene['chapters']:
            folder='ref2/scenes/scene/chapters/'+chapter['shot_id']
            manifest=json.loads(z.read(folder+'/references-and-guidance.json'))
            assert manifest['local_references']==chapter['local_references']
            assert all(r['path'] in z.namelist() for r in manifest['references'])
    assert store.project(pid)==before and store.jobs(pid)==jobs and store.assets(pid)==assets


def test_missing_prop_only_blocks_its_own_shot_and_refinement_checks_it(client,plan):
    pid=setup_props(client,plan,False);add_asset(pid,plan,'jug')
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    assert not scene['missing_references']
    assert not scene['chapters'][0]['missing_references'] and not scene['chapters'][0]['issues']
    assert scene['chapters'][1]['missing_references']==['Screwdriver']
    with pytest.raises(ValueError,match='Screwdriver'):
        engine.build_input(store.project(pid),models.JobRequest(capability='h3_scene',target_id='scene'))


def test_refinement_must_keep_prop_definitions_in_their_shot(client,plan):
    pid=setup_props(client,plan)
    scene=client.get('/api/projects/'+pid).json()['delivery']['scenes'][0]
    result={'global_prompt':scene['global_prompt'],'chapters':[{'shot_id':c['shot_id'],'shot_prompt':c['shot_prompt']} for c in scene['chapters']]}
    delivery.validate_result(result,scene,plan)
    bad=copy.deepcopy(result)
    bad['global_prompt']+='\n'+bad['chapters'][0]['shot_prompt'].split('summary:')[0]
    with pytest.raises(ValueError,match='公共參數'):delivery.validate_result(bad,scene,plan)
    bad=copy.deepcopy(result);bad['chapters'][0]['shot_prompt']='summary:'+bad['chapters'][0]['shot_prompt'].split('summary:',1)[1]
    with pytest.raises(ValueError,match='definitions'):delivery.validate_result(bad,scene,plan)


def test_prop_approval_changes_refinement_basis_and_slots_avoid_composition(client,plan):
    pid=setup_props(client,plan);add_asset(pid,plan,'start')
    config=delivery.configuration(pid);config['scenes']={'scene':{'chapters':{'shot':{'reference_frame':'start'}}}}
    p=store.project(pid);scene=delivery.scene_bundle(p,plan['scenes'][0],config)
    assert [r['label'] for r in scene['references']]==['Picture 1','Picture 2','Picture 3']
    assert scene['chapters'][0]['local_references'][0]['label']=='Picture 4'
    assert not scene['chapters'][0]['issues']
    with store.db() as c:c.execute("UPDATE assets SET status='rejected' WHERE project_id=? AND target_id='jug'",(pid,))
    changed=delivery.scene_bundle(p,plan['scenes'][0],config)
    assert changed['delivery_hash']!=scene['delivery_hash']
    assert changed['chapters'][1]['references']==scene['chapters'][1]['references']


def test_scene_prop_union_does_not_consume_every_shot_slots(client,plan):
    base=copy.deepcopy(plan['shots'][0]);plan['shots']=[]
    for i in range(10):
        eid='prop'+str(i);plan['canon'].append({'id':eid,'kind':'prop','name':'Prop '+str(i),'description':'Blue object','facts':[]})
        shot=copy.deepcopy(base);shot.update(id='shot'+str(i),keyframes=[{'id':'frame'+str(i),'moment':'start','description':'Moment'}]);shot['entity_ids'].append(eid);plan['shots'].append(shot)
    pid=create(client,plan)
    for e in plan['canon']:add_asset(pid,plan,e['id'])
    scene=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    assert len(scene['references'])==2
    assert all(len(c['references'])==3 and len(c['local_references'])==1 for c in scene['chapters'])
    assert not any('nine' in issue for c in scene['chapters'] for issue in c['issues'])


def test_existing_manual_text_is_preserved_and_flagged_when_prop_was_global(client,plan):
    pid=setup_props(client,plan)
    current=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    old_global=current['global_prompt']+'\n<Subject 3> is Water jug from <Picture 3>.'
    manual=current['chapters'][0]['shot_prompt']
    config=delivery.configuration(pid);config['scenes']={'scene':{'global_prompt':old_global,'prompt_edited':True,'chapters':{'shot':{'shot_prompt':manual,'prompt_edited':True}}}}
    store.put_setting('delivery:'+pid,config)
    result=delivery.scene_bundle(store.project(pid),plan['scenes'][0])
    assert result['global_prompt']==old_global and result['chapters'][0]['shot_prompt']==manual
    assert any('公共參數' in issue for issue in result['chapters'][0]['issues'])
