"""Astra-authored audition directions for 下一站：長洲, explicitly requested voices."""
import json,sys
from pathlib import Path
import httpx
BASE='http://127.0.0.1:4760'
PID='54809c31ce4144b4'
DIRECTIONS={
'c_leyan':('二十出頭香港青年男聲，中音略低、乾淨偏薄，咬字清楚，句尾收住，克制而警覺；疲憊時略帶氣聲，避免英雄式播音腔。','行。我落去睇吓，好快就返嚟。你喺屋企等我。'),
'c_chang':('約六十歲香港男人，低沉厚實、少許砂質喉音，胸腔共鳴，語速不快，短句俐落，有街坊長輩的親切和實幹感。','樂仔，行未？跟住我，慢慢落，睇清楚先好行。'),
'c_mother':('五十八歲香港母親聲線，中音偏低、稍微沙啞，柔和但不嬌弱；略乏氣，說話有生活感，關心時輕輕提高句尾。','你隻手做咩？食咗嘢先啦，唔使成日掛住我。'),
'c_wong':('四十多歲香港女聲，原本聲線偏薄、略緊，乾澀帶氣聲；這是音色試音，清晰說話，不加入感染尖叫或暴力聲效。','我喺呢度。你聽唔聽到我講嘢？'),
'c_guard':('中年香港男人，中低音，粗厚略沙啞，短促直接、字頭有力，警惕而壓住音量；街坊語氣，不用專業保安播報腔。','有冇嘢？排好隊，一個一個嚟，唔好急。'),
'c_queue_man':('成年香港男聲，中高音、略帶鼻腔共鳴，音色偏薄，語速較快，疑問句上揚；焦慮但仍盡量壓低聲音。','聽講朗屏嗰邊有人過嚟。長洲？咁我哋點去呀？'),
'c_queue_woman':('中年香港女聲，中音明亮、結實，咬字俐落，說話節奏稍快，語氣帶懷疑及日常街坊直率感，不尖銳誇張。','有人話屯門仲有軍隊。你肯定聽清楚咩？'),
'c_neighbors':('香港街坊群的單一成年男性代表試音，中音樸實、略疲倦、低聲克制；只作群眾其中一條聲線參考，群像需另製多聲軌，勿合成多人齊聲。','大家細聲啲，聽吓佢講乜先。'),
'c_door_woman':('成年香港母親女聲，中高音、氣促沙啞，緊張而壓住哭腔，呼吸較短，字尾微顫；保留清晰咬字，避免失控尖叫。','開門，求下你。我想搵人幫手，你聽唔聽到？'),
'c_child':('香港幼童聲線，音調自然偏高、柔細，呼吸短、字音稚嫩清楚；這是中性音色試音，不加痛苦哭叫，不模仿任何真人。','媽媽，我喺呢度。你可唔可以陪住我？'),
'c_official':('成年香港男播報員，低中音沉穩，咬字端正、節奏平均、語調平直，克制而疏離；先保留乾淨人聲，收音機失真於後製另加。','請各位市民留意。避免前往主要道路，保持冷靜。'),
'c_radio_man':('成年香港男人，中音偏低，乾澀、近咪，語速急但字音清楚，呼吸急促，緊張而努力讓對方聽清；先保留乾聲，電台雜訊另加。','有冇人收到？我再講一次，長洲仲有人。聽到請回答。')}

def main():
    c=httpx.Client(base_url=BASE,timeout=30);p=c.get('/api/projects/'+PID);p.raise_for_status();p=p.json();records=[]
    for e in p['production']['canon']:
        if e['kind']!='character' or e['id'] not in DIRECTIONS:continue
        v=next(v for v in p['postproduction']['profiles'] if v['character_id']==e['id'])
        if v['version']!=0:continue # Never overwrite user edits or repeat generation.
        description,text=DIRECTIONS[e['id']]
        r=c.put(f'/api/projects/{PID}/voices/{e["id"]}',json={'version':0,'description':description,'language':'粵語（香港）','sample_text':text,'seed':42+len(records)*101});r.raise_for_status();v=r.json()
        r=c.post(f'/api/projects/{PID}/voices/{e["id"]}/generate',json={'version':v['version']});r.raise_for_status();records.append({'character':e['name'],'id':e['id'],'take_id':r.json()['id']})
    Path('data/acceptance/voxcpm/live-voices.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print(json.dumps(records,ensure_ascii=False))

if __name__=='__main__':main()
