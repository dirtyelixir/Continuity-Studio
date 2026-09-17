"""Recoverable project deletion; no files or dependent records are removed."""
from . import store


def list_projects(deleted=False):
    with store.db() as c:
        return [dict(r) for r in c.execute(
            'SELECT id,title,idea,style,revision,deleted_at,created,updated FROM projects '
            + ('WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC' if deleted else
               'WHERE deleted_at IS NULL ORDER BY updated DESC'))]


def delete(pid, confirmation_title, revision):
    """Caller holds engine.LOCK, shared with image/text/voice submission."""
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not p: raise ValueError('找不到作品。')
        if p['deleted_at'] is not None: raise ValueError('作品已在已刪除作品清單。')
        if p['title']!=confirmation_title: raise ValueError('作品名稱不相符，請輸入完整作品名稱。')
        if p['revision']!=revision: raise ValueError('作品版本已更新，請取消並重新開啟刪除確認。')
        if c.execute("SELECT 1 FROM jobs WHERE project_id=? AND state IN ('queued','running','awaiting_input') LIMIT 1",(pid,)).fetchone():
            raise ValueError('此作品仍有生成、排隊或等待提交的工作，請完成或取消後再刪除。')
        if c.execute("SELECT 1 FROM voice_takes WHERE project_id=? AND state IN ('queued','running','importing') LIMIT 1",(pid,)).fetchone():
            raise ValueError('此作品仍有配音或匯入工作，請完成後再刪除。')
        if c.execute("SELECT 1 FROM video_takes WHERE project_id=? AND state IN ('queued','preparing','submitting','submitted','running','uncertain','recoverable') LIMIT 1",(pid,)).fetchone():
            raise ValueError('此作品仍有影片生成或待回收工作，請完成後再刪除。')
        c.execute('UPDATE projects SET deleted_at=? WHERE id=?',(store.now(),pid))
        store.event(c,pid,'project_deleted',p['title'])
    return {'ok':True,'deleted_project_id':pid}


def restore(pid):
    """Caller holds engine.LOCK. The original production remains untouched."""
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not p: raise ValueError('找不到作品。')
        if p['deleted_at'] is None: raise ValueError('此作品尚未刪除。')
        c.execute('UPDATE projects SET deleted_at=NULL WHERE id=?',(pid,))
        store.event(c,pid,'project_restored',p['title'])
    return {'ok':True,'restored_project_id':pid}
