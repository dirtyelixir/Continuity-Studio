"""Overflow count-label wording: conservative UTF-8 byte upper bound vs native measured tokens."""
import json
import pytest
from studio import context_limits as limits


def test_input_count_label_distinguishes_measured_tokens_from_upper_bound():
    measured=limits.input_count_label(430493,'chat-template-tokenizer')
    upper=limits.input_count_label(430493,'utf8-byte-upper-bound')
    assert measured=='實際核對 430,493 tokens'
    assert upper=='UTF-8 位元組保守上界 430,493（非精確 token 數）'
    assert '保守上界' not in measured and '非精確 token 數' not in measured
    assert '保守上界' in upper and '非精確 token 數' in upper
    assert '430,493' in measured and '430,493' in upper


def test_overflow_error_labels_both_methods_and_keeps_preservation_text():
    policy={'max_output_tokens':32768,'context_window':131072}
    measured=limits.overflow_error(430493,'chat-template-tokenizer',policy)
    upper=limits.overflow_error(430493,'utf8-byte-upper-bound',policy)
    for text in (measured,upper):
        assert text.startswith('必要上下文超出所選模型預算（輸入')
        assert '430,493' in text and '預留輸出 32768' in text and '容量 131072' in text
        assert '已保存成果保留，未截斷原文或切換服務商。' in text
    assert '實際核對' in measured and '保守上界' not in measured
    assert 'UTF-8 位元組保守上界' in upper and '非精確 token 數' in upper


def test_overflow_error_from_check_uses_clarified_label_and_preserves_receipt(tmp_path):
    p={'kind':'http','context_policy':limits.freeze({'kind':'http','context_window':4096,'max_output_tokens':512})}
    prompt='原文不得改寫。'*1000
    with pytest.raises(ValueError,match=r'UTF-8 位元組保守上界 \d[\d,]*（非精確 token 數）'):
        limits.check(p,prompt,{},tmp_path)
    receipt=json.loads((tmp_path/'context-budget.json').read_text())
    assert not receipt['fits'] and receipt['count_method']=='utf8-byte-upper-bound'
