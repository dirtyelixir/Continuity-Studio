"""Independent bounded lanes; a renderer cannot occupy a text worker."""
from concurrent.futures import ThreadPoolExecutor

from . import store

LANES = {'text': ('文字工作', 2), 'chapter': ('長篇分鏡', 1), 'image': ('圖片生成', 1)}


def lane(job):
    if job['capability'] == 'image':
        return 'image'
    return 'chapter' if job.get('input', {}).get('chapter_pipeline') else 'text'


class JobPool:
    def __init__(self):
        self.pools = {key: ThreadPoolExecutor(max_workers=limit, thread_name_prefix='studio-' + key)
                      for key, (_, limit) in LANES.items()}

    def submit(self, fn, jid):
        return self.pools[lane(store.job(jid))].submit(fn, jid)

    def shutdown(self, **kwargs):
        for pool in self.pools.values():
            pool.shutdown(**kwargs)


def snapshot():
    """Project views disclose the global lane, including work in other projects."""
    with store.db() as c:
        rows = c.execute('''SELECT j.id,j.capability,j.state,p.title,
            json_extract(j.input,'$.chapter_pipeline') AS chapter
            FROM jobs j JOIN projects p ON p.id=j.project_id
            WHERE j.state IN ('queued','running') ORDER BY j.updated,j.created,j.id''').fetchall()
    groups = {key: [] for key in LANES}
    for row in rows:
        groups[lane({'capability': row['capability'], 'input': {'chapter_pipeline': row['chapter']}})].append(row)
    result = {}
    for key, jobs in groups.items():
        running = [j for j in jobs if j['state'] == 'running']
        position = 0
        for job in jobs:
            if job['state'] == 'queued':
                position += 1
            result[job['id']] = {'lane': key, 'label': LANES[key][0], 'capacity': LANES[key][1],
                'position': position if job['state'] == 'queued' else None,
                'running': len(running), 'running_projects': list(dict.fromkeys(j['title'] for j in running))}
    return result
