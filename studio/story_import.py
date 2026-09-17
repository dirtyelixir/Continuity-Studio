"""Bounded text/DOCX preview. Never extracts archives or starts generation."""
import io
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

MAX_FILE_BYTES=2_000_000
MAX_TEXT_CHARS=20000
MAX_XML_BYTES=4_000_000
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def _valid_text(text):
    if not text.strip(): raise ValueError('檔案沒有可讀文字，請貼上劇情內容。')
    if len(text)>MAX_TEXT_CHARS: raise ValueError('文字超過 20,000 字，請按單集或場景分開導入。')
    if any(unicodedata.category(c)=='Cc' and c not in '\n\r\t' for c in text):
        raise ValueError('檔案含二進位或不支援的控制字元，請另存為文字檔。')
    return text

def _docx(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            infos=z.infolist()
            if len(infos)>2000 or sum(i.file_size for i in infos)>20_000_000:
                raise ValueError('Word 檔案展開後過大，請只導入所需的劇本內容。')
            if any(i.flag_bits&1 for i in infos): raise ValueError('不支援加密的 Word 檔案。')
            docs=[i for i in infos if i.filename=='word/document.xml']
            if len(docs)!=1: raise ValueError('Word 檔案缺少有效正文。')
            if docs[0].file_size>MAX_XML_BYTES: raise ValueError('Word 正文過大，請分開導入。')
            with z.open(docs[0]) as f:raw=f.read(MAX_XML_BYTES+1)
            if len(raw)>MAX_XML_BYTES: raise ValueError('Word 正文過大，請分開導入。')
        xml=raw.decode('utf-8-sig')
        if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
            raise ValueError('Word 檔案含不支援的 XML 宣告。')
        root=ET.fromstring(xml)
        body=root.find(W+'body')
        if root.tag!=W+'document' or body is None: raise ValueError('Word 檔案缺少有效正文。')
        paragraphs=[]
        for p in body.iter(W+'p'):
            parts=[]
            for node in p.iter():
                if node.tag==W+'t':parts.append(node.text or '')
                elif node.tag==W+'tab':parts.append('\t')
                elif node.tag in [W+'br',W+'cr']:parts.append('\n')
            paragraphs.append(''.join(parts))
        return '\n'.join(paragraphs)
    except (zipfile.BadZipFile,KeyError,ET.ParseError,UnicodeError,RuntimeError,NotImplementedError,EOFError,OSError):
        raise ValueError('無法讀取此 Word 檔案，請另存為 DOCX 或貼上文字。') from None

def extract_story(filename,content):
    if len(content)>MAX_FILE_BYTES: raise ValueError('檔案超過 2 MB，請分開導入。')
    filename=filename.replace('\\','/').split('/')[-1]
    filename=''.join(c for c in filename if unicodedata.category(c)!='Cc')[:255]
    ext=filename.rsplit('.',1)[-1].lower() if '.' in filename else ''
    if ext not in ['txt','md','docx']: raise ValueError('請選擇 TXT、Markdown 或 Word DOCX；PDF 請先複製文字。')
    if ext=='docx':text=_docx(content)
    else:
        try:text=content.decode('utf-16' if content.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
        except UnicodeError: raise ValueError('文字編碼無法讀取，請另存為 UTF-8，或直接貼上文字。') from None
    return {'text':_valid_text(text),'filename':filename,'format':ext}
