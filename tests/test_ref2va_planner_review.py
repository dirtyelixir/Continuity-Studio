"""Selector prompt contract; real provider evidence lives in reviews/autonomous-ref2va-20260914."""
from studio import models,store,video_workflow as video
from test_production import client,plan,create

def test_selection_prompt_distinguishes_reference_need_from_frame_count(client,plan):
    pid=create(client,plan)
    data=video.build(store.project(pid),models.JobRequest(capability='h3_strategy',target_id='shot'))
    for phrase in ['not storyboard count','appearance_consistency','opening composition is insufficient','reference_demands','smallest necessary set','timestamp-critical intermediate state']:
        assert phrase in data['prompt']
    assert 'USER SELECTED MODE:' not in data['prompt']
    assert data['video_source']['conditioning_contract']==1
