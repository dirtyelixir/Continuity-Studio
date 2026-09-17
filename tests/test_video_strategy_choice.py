import pytest
from studio import store,models,video_workflow as video
from test_production import client,plan,create


def test_strategy_choice_is_frozen_distinct_and_enforced(client,plan):
    pid=create(client,plan);p=store.project(pid)
    auto=video.build(p,models.JobRequest(capability='h3_strategy',target_id='shot'))
    chosen=video.build(p,models.JobRequest(capability='h3_strategy',target_id='shot',strategy_mode='FL2VA'))
    assert auto['strategy_mode']=='AUTO' and chosen['strategy_mode']=='FL2VA'
    assert auto['video_hash']==chosen['video_hash']
    assert auto['video_request_hash']!=chosen['video_request_hash']
    assert 'USER SELECTED MODE: FL2VA' in chosen['prompt']
    with pytest.raises(ValueError,match='指定的模式'):
        video.validate_strategy({'mode':'I2VA'},chosen['video_source'],'FL2VA')
    with pytest.raises(ValueError):
        models.JobRequest(capability='h3_strategy',strategy_mode='other')
    assert not video.config(pid)['shots']
