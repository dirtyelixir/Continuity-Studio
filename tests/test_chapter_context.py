import copy
import json
import pytest
from studio import chapter_context as cc, chapter_pipeline as cp, context_limits as limits, providers, store
from test_production import plan


@pytest.fixture
def context_case(plan):
    writing=copy.deepcopy(plan)
    writing['scenes'].append({**copy.deepcopy(writing['scenes'][0]),'id':'later','title':'Return to the locked door'})
    units=[{'id':f'P{i}','text':('The brass key must stay with Ada until sunset.' if i==0 else 'Ada returns to the locked door.' if i==100 else 'Background original passage '+str(i)+': '+'雨落在屋外。'*60)} for i in range(101)]
    inp={'provider_config':{'id':'test','kind':'http','model':'test','context_policy':limits.freeze({'kind':'http','context_window':16000,'max_output_tokens':2048})},
         'context_instructions':'MANDATORY STUDIO PRODUCTION METHOD: preserve exact source and canon.',
         'source':{'units':units,'source_text':'\n'.join(u['text'] for u in units),'source_kind':'story'},
         'feedback':'Keep the late reveal.', 'serial_source':{'outline':'A key is planted early and recovered at sunset.'}}
    job={'id':'isolated-context','input':inp,'capability':'storyboard'}
    scope={'writing':writing,'scene_ids':['later'],'requested_scene':writing['scenes'][1],
           'previous_shot':[writing['shots'][0]],'maximum_shots':2}
    return job,scope,units


def index_provider(monkeypatch,calls):
    def run(provider,kind,prompt,images,work):
        calls.append((kind,work.name))
        assert kind=='chapter_source_index'
        units=json.loads(prompt.split('REQUESTED SOURCE UNITS:\n')[1].split('\nONE STRUCTURAL CORRECTION:')[0])
        spans=[]
        for u in units:
            scene='later' if u['id']=='P100' else 'scene_workshop'
            # Fixture actual scene ID is read from the saved catalog.
            catalog=json.loads(prompt.split('SAVED SCENES:\n')[1].split('\nREQUESTED SOURCE UNITS:')[0])
            if scene!='later':scene=catalog[0]['id']
            spans.append({'first_id':u['id'],'last_id':u['id'],'scene_ids':[scene], 'recall_source_ids':['P0'] if scene=='later' else []})
        return {'summary':'Original source navigation for this batch. The locked door returns later.', 'spans':spans,
                'anchors':[{'source_id':'P0','quote':'The brass key must stay with Ada until sunset.'}] if units[0]['id']=='P0' else []}
    monkeypatch.setattr(providers,'run',run)


def test_short_context_recalls_early_anchor_preserves_states_and_reuses_index(context_case,tmp_path,monkeypatch):
    job,scope,units=context_case;calls=[];index_provider(monkeypatch,calls)
    original='Full chapter request:\n'+store.encode(units)
    status={'next_label':'正在規劃場景','completed':1}
    prompt,receipt=cc.adapt(job,tmp_path,'02-scene','chapter_scene',original,scope,status)
    assert receipt['mode']=='scoped' and receipt['selected_source_ids']==['P0','P100']
    payload=json.loads(prompt.split('FROZEN CONTEXT PACK:\n')[1])
    assert payload['exact_source_units']==[units[0],units[100]]
    assert payload['authoritative_canon']==scope['writing']['canon']
    assert payload['frozen_screenplay']==scope['writing']['screenplay']
    assert payload['previous_shot']==scope['previous_shot']
    assert payload['director_feedback']=='Keep the late reveal.'
    assert len(payload['source_navigation'])==len(calls)
    assert limits.fits(receipt['input_tokens'],job['input']['provider_config']['context_policy'])
    before={p.name:p.read_bytes() for p in tmp_path.glob('*checkpoint.json')};calls.clear()
    assert cc.adapt(job,tmp_path,'02-scene','chapter_scene',original,scope,status)==(prompt,receipt)
    assert calls==[] and all((tmp_path/n).read_bytes()==v for n,v in before.items())
    assert status['next_label']=='正在規劃場景'


def test_long_context_keeps_entire_request_without_index(context_case,tmp_path,monkeypatch):
    job,scope,units=context_case
    job['input']['provider_config']['context_policy']=limits.freeze({'kind':'deepseek'})
    def forbidden(*a):raise AssertionError('No index needed')
    monkeypatch.setattr(providers,'run',forbidden)
    original=store.encode(units)
    prompt,receipt=cc.adapt(job,tmp_path,'02-scene','chapter_scene',original,scope,{'next_label':'x'})
    assert prompt==original and receipt['mode']=='full'
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('problem',['anchor','missing_unit','foreign_scene','foreign_recall'])
def test_index_rejects_ungrounded_or_incomplete_maps(context_case,tmp_path,monkeypatch,problem):
    job,scope,units=context_case;calls=[];index_provider(monkeypatch,calls);original=providers.run
    def bad(*args):
        result=original(*args)
        if problem=='anchor':result['anchors']=[{'source_id':'P0','quote':'Invented key ownership'}]
        if problem=='missing_unit':result['spans'].pop()
        if problem=='foreign_scene':result['spans'][0]['scene_ids']=['missing']
        if problem=='foreign_recall':result['spans'][0]['recall_source_ids']=['other-source']
        return result
    monkeypatch.setattr(providers,'run',bad)
    with pytest.raises(ValueError):cc.adapt(job,tmp_path,'02-scene','chapter_scene',store.encode(units),scope,{'next_label':'x'})
    assert len(calls)==2 and not list(tmp_path.glob('*checkpoint.json'))


def test_required_context_is_never_cut_to_force_fit(context_case,tmp_path,monkeypatch):
    job,scope,units=context_case;calls=[];index_provider(monkeypatch,calls)
    scope['scene_ids']=[s['id'] for s in scope['writing']['scenes']]
    with pytest.raises(ValueError,match='未截走關鍵背景'):
        cc.adapt(job,tmp_path,'02-scene','chapter_scene',store.encode(units),scope,{'next_label':'x'})
    assert list(tmp_path.glob('*checkpoint.json'))  # Index work survives the block.
    r=json.loads((tmp_path/'02-scene-context-selection.json').read_text())
    assert r['selected_source_ids']==[u['id'] for u in units]


def test_cancelled_index_stops_without_saving_provider_result(context_case,tmp_path,monkeypatch):
    job,scope,units=context_case;calls=[];index_provider(monkeypatch,calls);original=providers.run
    def cancel(*args):
        value=original(*args);(tmp_path/'cancel-requested').touch();return value
    monkeypatch.setattr(providers,'run',cancel)
    with pytest.raises(RuntimeError,match='取消'):
        cc.adapt(job,tmp_path,'02-scene','chapter_scene',store.encode(units),scope,{'next_label':'x'})
    assert not list(tmp_path.glob('*checkpoint.json'))


def test_index_partition_tampering_is_rejected(context_case,tmp_path,monkeypatch):
    job,scope,units=context_case;calls=[];index_provider(monkeypatch,calls)
    cc.adapt(job,tmp_path,'02-scene','chapter_scene',store.encode(units),scope,{'next_label':'x'})
    p=tmp_path/'context-index-partition.json';data=json.loads(p.read_text());data['batches'][0].pop();cp.atomic_json(p,data)
    calls.clear()
    with pytest.raises(ValueError,match='不符'):
        cc.adapt(job,tmp_path,'02-scene','chapter_scene',store.encode(units),scope,{'next_label':'x'})
    assert calls==[]


def test_foundation_deduplicates_without_summarizing_source(context_case,tmp_path):
    job,scope,units=context_case
    small=units[:2];job['input']['source']={'source_kind':'story','source_text':'\n'.join(u['text'] for u in small),'units':small}
    prompt,receipt=cc.adapt(job,tmp_path,'01-writing','chapter_writing','old duplicated prompt '*2000,{'foundation':True},{'next_label':'x'})
    assert receipt['mode']=='deduplicated-foundation'
    payload=json.loads(prompt.split('AUTHORITATIVE FOUNDATION:\n')[1])
    assert payload['source']['source_text']==job['input']['source']['source_text']
    assert 'units' not in payload['source']


def test_scene_recalls_expand_all_original_units_with_transitive_closure():
    selected,scenes=cc.expand_recalls({'P3'},{'P3':['early'],'P1':['P0'],'P0':['P3']},{'early':['P1','P2']})
    assert selected=={'P0','P1','P2','P3'} and scenes==['early']
