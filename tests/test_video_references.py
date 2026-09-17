import copy
from studio import store,continuity,video_workflow as video
from test_production import client,plan,create,add_asset


def test_reference_cards_match_generation_scope_and_asset_readiness(client,plan):
    plan['canon'] += [
        {'id':'jug','kind':'prop','name':'Jug','description':'Blue jug','facts':[]},
        {'id':'driver','kind':'prop','name':'Driver','description':'Long tool','facts':[]},
        {'id':'radio','kind':'voice','name':'Radio','description':'Offscreen broadcast','facts':[]}]
    plan['shots'][0]['entity_ids']+=['jug','radio']
    pid=create(client,plan)
    first=add_asset(pid,plan,'ada')
    add_asset(pid,plan,'ada',status='pending')
    add_asset(pid,plan,'room',status='rejected')
    p=store.project(pid);rows=video.reference_cards(p,p['production']['shots'][0]);r={r['target_id']:r for r in rows}
    assert set(r)=={'ada','room','jug'}
    assert r['ada']['asset']['id']==first and r['ada']['ready']
    assert r['room']['status']=='rejected' and not r['room']['ready']
    assert r['jug']['status']=='missing'
    refs,missing=continuity.references(p['production'],store.assets(pid),'start')
    assert [x['asset']['id'] for x in rows if x['ready']]==[x['id'] for x in refs]
    assert [x['name'] for x in rows if not x['ready']]==missing
    p['production']['canon'][0]['description']+=' Changed appearance'
    assert video.reference_cards(p,p['production']['shots'][0])[0]['status']=='stale'
    (store.DATA/r['ada']['asset']['path']).unlink()
    p=store.project(pid)
    assert video.reference_cards(p,p['production']['shots'][0])[0]['status']=='missing_file'
