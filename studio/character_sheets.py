"""Character sheet policy, independent of existing identity approval/provenance."""
from . import crowds,store,continuity


def guide_path():
    return store.DATA/'guides'/'character-four-view-v2.jpg'


def verified(asset):
    return bool(asset and (asset.get('review') or {}).get('character_sheet')=='pass')


def project_status(p):
    entries=[]
    for entity in (p.get('production') or {}).get('canon',[]):
        if entity['kind']!='character':continue
        assets=[a for a in p['assets'] if a['target_id']==entity['id']]
        approved=continuity.approved_for(p['production'],assets,entity['id'])
        entries.append({'target_id':entity['id'],'name':entity['name'],'approved_asset_id':approved['id'] if approved else None,'status':'verified' if verified(approved) else 'needs_four_view','pending_asset_ids':[a['id'] for a in assets if a['status']=='pending']})
    return {'layout':continuity.CHARACTER_SHEET_LAYOUT,'guide_available':guide_path().is_file(),'characters':entries}


def requirements_markdown():
    return '# Individual character references — required four-view sheet\n\n'+continuity.CHARACTER_SHEET_INSTRUCTION+'\n\n## Crowd references\n\n'+crowds.IMAGE+' '+crowds.REFERENCE+'\n\nThe saved user example controls layout only, never character identity or style. Existing portraits remain in history and as identity sources until a new sheet is reviewed and approved. Character approvals require a passing four-view review or explicit human acknowledgement with an automatically saved acceptance record. Human acceptance never changes the original review verdict. Replacing an approved identity follows normal dependency invalidation.\n'
