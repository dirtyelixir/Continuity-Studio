import io
import zipfile
import pytest
from studio import story_import as mod

def docx(xml):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('word/document.xml',xml)
    return out.getvalue()

def test_docx_text_tables_breaks_and_unicode():
    xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t xml:space="preserve">  第一幕 </w:t><w:tab/><w:t>夜</w:t><w:br/><w:t>雨</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>甲：你好。</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:r><w:t>終</w:t></w:r></w:p></w:body></w:document>'
    result=mod.extract_story('../劇本.docx',docx(xml))
    assert result=={'filename':'劇本.docx','format':'docx','text':'  第一幕 \t夜\n雨\n甲：你好。\n終'}

@pytest.mark.parametrize('encoding',['utf-8','utf-8-sig','utf-16'])
def test_bom_and_exact_whitespace(encoding):
    text='  劇本\r\n甲：你好。\t\n'
    assert mod.extract_story('C:\\folder\\劇本.TXT',text.encode(encoding))=={'filename':'劇本.TXT','format':'txt','text':text}

@pytest.mark.parametrize('name,data',[
    ('x.txt',b''),('x.txt',b' \n'),('x.txt',b'abc\0def'),('x.md',b'\x81\x82'),
    ('x.pdf',b'%PDF'),('x.docx',b'not a zip'),
    ('x.docx',docx('<!DOCTYPE a [<!ENTITY b "bad">]><a>&b;</a>')),
    ('x.docx',docx('<broken>')),('x.docx',docx('<a/>')),
    ('x.txt',b'x'*20001),('x.txt',b'x'*2000001)])
def test_bad_input_rejected(name,data):
    with pytest.raises(ValueError):mod.extract_story(name,data)

def test_expanded_xml_limit(monkeypatch):
    monkeypatch.setattr(mod,'MAX_XML_BYTES',100)
    with pytest.raises(ValueError,match='過大'):mod.extract_story('x.docx',docx('x'*101))

def test_duplicate_document_rejected():
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('word/document.xml','<x/>')
        with pytest.warns(UserWarning):z.writestr('word/document.xml','<x/>')
    with pytest.raises(ValueError):mod.extract_story('x.docx',out.getvalue())
