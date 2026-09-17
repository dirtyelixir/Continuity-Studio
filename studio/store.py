import json, sqlite3, uuid, os, hashlib
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.environ.get('STUDIO_DATA', ROOT/'data')).resolve()

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex[:16]
def encode(x): return json.dumps(x,ensure_ascii=False,sort_keys=True)
def digest(x): return hashlib.sha256(encode(x).encode()).hexdigest()

@contextmanager
def db():
    DATA.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(DATA/'studio.sqlite3',timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

def init():
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,title TEXT NOT NULL,idea TEXT NOT NULL,style TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0,production TEXT,created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),number INTEGER NOT NULL,production TEXT NOT NULL,reason TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(project_id,number));
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),capability TEXT NOT NULL,target_id TEXT NOT NULL,state TEXT NOT NULL,provider TEXT NOT NULL,input TEXT NOT NULL,result TEXT,error TEXT NOT NULL DEFAULT '',created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),target_id TEXT NOT NULL,kind TEXT NOT NULL,path TEXT NOT NULL,status TEXT NOT NULL,dependency_hash TEXT NOT NULL,reference_ids TEXT NOT NULL,prompt TEXT NOT NULL,provider TEXT NOT NULL,job_id TEXT,review TEXT,note TEXT NOT NULL DEFAULT '',created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL REFERENCES projects(id),kind TEXT NOT NULL,detail TEXT NOT NULL,created TEXT NOT NULL);
        ''')
        columns={r['name'] for r in c.execute('PRAGMA table_info(assets)')}
        if 'source_asset_id' not in columns: c.execute("ALTER TABLE assets ADD COLUMN source_asset_id TEXT NOT NULL DEFAULT ''")
        project_columns={r['name'] for r in c.execute('PRAGMA table_info(projects)')}
        if 'source_kind' not in project_columns: c.execute("ALTER TABLE projects ADD COLUMN source_kind TEXT NOT NULL DEFAULT 'idea'")
        if 'source_filename' not in project_columns: c.execute("ALTER TABLE projects ADD COLUMN source_filename TEXT NOT NULL DEFAULT ''")
        if 'brief_revision' not in project_columns: c.execute("ALTER TABLE projects ADD COLUMN brief_revision INTEGER NOT NULL DEFAULT 0")
        if 'deleted_at' not in project_columns: c.execute("ALTER TABLE projects ADD COLUMN deleted_at TEXT")
        c.execute('CREATE TABLE IF NOT EXISTS story_chapters(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),number INTEGER NOT NULL,title TEXT NOT NULL,brief TEXT NOT NULL,source_kind TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL,updated TEXT NOT NULL,UNIQUE(project_id,number))')
        # Queued jobs have not entered execute(); preserve their original frozen
        # inputs and IDs for startup dispatch. Never auto-resubmit running work.
        c.execute("UPDATE jobs SET state='interrupted',error='Application restarted while this job was in flight. Review existing output before retrying.',updated=? WHERE state='running'",(now(),))

def row(r):
    if r is None: return None
    d=dict(r)
    for k in ['production','input','result','reference_ids','review']:
        if k in d and d[k] is not None: d[k]=json.loads(d[k])
    return d

def project(pid, include_deleted=False):
    with db() as c:
        p=row(c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone())
    if not p: raise ValueError('找不到作品。')
    if p['deleted_at'] is not None and not include_deleted:
        raise ValueError('作品已刪除，請先到作品管理的「已刪除作品」還原。')
    return p

def assets(pid):
    with db() as c: return [row(r) for r in c.execute('SELECT * FROM assets WHERE project_id=? ORDER BY created DESC',(pid,))]

_job_reads = ContextVar('studio_job_reads', default=None)

def reuse_job_reads(fn):
    """Reuse decoded job history only during one read-only response, never across requests."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = _job_reads.set({})
        try:
            return fn(*args, **kwargs)
        finally:
            _job_reads.reset(token)
    return wrapped

def jobs(pid):
    cache = _job_reads.get()
    if cache is not None and pid in cache:
        return cache[pid]
    with db() as c:
        result = [row(r) for r in c.execute('SELECT * FROM jobs WHERE project_id=? ORDER BY created DESC',(pid,))]
    if cache is not None:
        cache[pid] = result
    return result

def job(jid):
    with db() as c: j=row(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
    if not j: raise ValueError('Job not found')
    return j

def event(c,pid,kind,detail): c.execute('INSERT INTO events(project_id,kind,detail,created) VALUES(?,?,?,?)',(pid,kind,detail,now()))

def setting(key,default=None):
    with db() as c: r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return json.loads(r[0]) if r else default

def put_setting(key,value):
    with db() as c: c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,encode(value)))
