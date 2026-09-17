#!/usr/bin/env python3
"""Back up and reorganize one project. The studio server must be stopped first."""
import argparse,fcntl,hashlib,json,sqlite3,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio import store,asset_library
parser=argparse.ArgumentParser();parser.add_argument('project_id');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
if not args.apply:parser.error('Use --apply after stopping the studio server; a backup is made before changes.')
lease=(store.DATA/'server.lock').open('a')
try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Stop the studio server before organizing originals.')
assert not [j for j in store.jobs(args.project_id) if j['state'] in ['running','queued']], 'Active generation must finish first'
before=store.assets(args.project_id)
backup=store.DATA/'backups'/('asset-library-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'));backup.mkdir(parents=True)
source=sqlite3.connect(store.DATA/'studio.sqlite3');copy=sqlite3.connect(backup/'studio.sqlite3');source.backup(copy);copy.close();source.close()
with zipfile.ZipFile(backup/'original-images.zip','w',zipfile.ZIP_DEFLATED) as z:
    for a in before:z.write(store.DATA/a['path'],a['path'])
(backup/'before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2))
moves=asset_library.migrate_project(args.project_id)
after={a['id']:a for a in store.assets(args.project_id)}
for a in before:
    assert {k:v for k,v in a.items() if k!='path'}=={k:v for k,v in after[a['id']].items() if k!='path'}
for m in moves:
    old=store.DATA/m['old'];new=store.DATA/m['new']
    assert old.is_symlink() and old.resolve()==new.resolve()
    assert hashlib.sha256(new.read_bytes()).hexdigest()==m['sha256']
report={'result':'PASS','project_id':args.project_id,'images_preserved':len(before),'images_organized':len(moves),'library':str(asset_library.write_catalog(args.project_id)),'backup':str(backup),'moves':moves}
(backup/'migration-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
