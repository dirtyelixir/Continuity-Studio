import copy
import pytest
from studio import h3_render_prompt as p

MOTION='camera_motion_h3_lora_v1_3000_pruned.safetensors'
REALISM='h3-realism-people-t2v-i2v-r2v.safetensors'

@pytest.mark.parametrize('mode',['I2VA','FL2VA','REF2VA'])
def test_automatic_prefixes_preserve_source_and_dialogue(mode):
    source={'mode':mode,'text':'For the target video...\nintegrated_multimodal_description:\n<d>行啦。</d>\noverall_soundscape: wind','global_prompt':'Scene description' if mode=='REF2VA' else ''}
    original=copy.deepcopy(source)
    settings={'other_loras':[{'name':MOTION,'strength':.9},{'name':REALISM,'strength':1}]}
    result=p.assemble(source,settings)
    target='global_prompt' if mode=='REF2VA' else 'text'
    assert result[target]=='camera motion; r34l1sm\n\n'+source[target]
    assert source==original and result['loras'][0]['strength']==.9
    assert p.assemble(source,{'other_loras':[]})['text']==source['text']
    again=p.assemble(p.generation_source(source,result),settings)
    assert again[target]==result[target] and not again['added_triggers']


def test_existing_leading_trigger_unknown_and_body_mentions():
    settings={'other_loras':[{'name':MOTION,'strength':1},{'name':REALISM,'strength':1},{'name':'unknown_h3.safetensors','strength':1}]}
    source={'mode':'I2VA','text':'CAMERA MOTION; r34l1sm\n\n<d>camera motion</d>','global_prompt':''}
    assert p.assemble(source,settings)['text']==source['text']
    source['text']='<d>camera motion</d>'
    assert p.assemble(source,settings)['text']=='camera motion; r34l1sm\n\n<d>camera motion</d>'
    source.update(mode='REF2VA')
    assert p.assemble(source,settings)['prefix_target']=='text'
