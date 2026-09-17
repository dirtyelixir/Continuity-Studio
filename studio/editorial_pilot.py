"""Authored one-scene pilot, explicitly based on the user's existing screenplay.

This is a reviewable editorial candidate, not a provider-generated or approved result.
No media generation is performed here.
"""
import copy
from . import editorial, models, store


def build(p):
    plan = editorial.complete_edits(models.Production.model_validate(p['production']).model_dump())
    scene = next((s for s in plan['scenes'] if s['title']=='十二樓一隻'),None)
    if not scene:
        raise ValueError('此試行需要原作「十二樓一隻」場景。')
    sid=scene['id']; old=[s for s in plan['shots'] if s['scene_id']==sid]
    if [s['title'] for s in old] != ['逐層聽','熟人的背影','石粒','折返','唔再問名字']:
        raise ValueError('原場景已改動，請按新版重新撰寫試行，不能套用舊範本。')
    prefix=sid+'__pilot_'; shots=[]; edits=[]; notes={}
    jug={'entity_id':'p_jug','key':'status','value':'empty; held in 陳樂言’s left hand'}
    def state(e,k,v): return {'entity_id':e,'key':k,'value':v}
    def add(source, suffix, title, duration, keep, purpose, framing, camera, blocking,
            beats, before, after, dialogue, sound, evidence, event, cut):
        s=copy.deepcopy(source)
        s.update(id=prefix+suffix,title=title,duration=duration,generation_duration=duration,
            shot_purpose=purpose,framing='16:9 live-action cinematic realism; natural skin tones; readable low light. '+framing,
            angle='Eye level, on the original side of the stairwell axis.',camera=camera,
            blocking=blocking,action=' '.join(b[2] for b in beats),
            expression='Restrained, physically specific reactions; no theatrical poses.',
            beats=[dict(start=a,end=b,action=c) for a,b,c in beats],start_state=before,end_state=after,
            dialogue=dialogue,soundscape=sound,music='None.',transition_note=cut,
            keyframes=[dict(id=prefix+suffix+'_start',moment='start',
                description=framing+' '+blocking+' A single frozen opening instant. Night skylight through narrow vents; all electric lights off.')])
        s['direction']=dict(beat_ids=[prefix+suffix+'_beat'],subject_ids=[i for i in s['entity_ids'] if i.startswith('c_')],
            visual_carrier=evidence,readability='文字規劃待看片驗證；文字卡不證明構圖、表演或嘴形。',
            cut_in_reason=cut,cut_out_reason=purpose+'完成後才離開；實際出點看片再定。',
            next_shot_relationship='維持同一側樓梯軸線；下行畫右，逃走畫左。')
        shots.append(s)
        edits.append(dict(id=prefix+suffix+'_edit',shot_id=s['id'],planned_edit_in=0,planned_edit_out=keep,
            cut_in_reason=cut,cut_out_reason=s['direction']['cut_out_reason'],continuity_note=s['transition_note']))
        notes[s['id']]=dict(source_shot_id=source['id'],story_order=len(shots),
            state_in_ref=editorial.state_refs(s)['start_state'],state_out_ref=editorial.state_refs(s)['end_state'],
            change_event={'source_excerpt':event,'authority':'原有已採用分鏡；試行未採用','kind':'story_action'},
            evidence={'goal':'action_or_reaction','carrier':evidence,'status':'unreviewed','media_status':'unreviewed'},
            no_cut_reason='本鏡是一個連續機位；不用額外特寫填滿鏡頭種類。')
        return s
    for floor in (19,17,14):
        add(old[0],'floor'+str(floor),str(floor)+'樓 · 聽',4,1.5,'以樓層變化表達下樓時間省略',
            '35mm medium wide; rail foreground, both men midground, floor '+str(floor)+' sign at the rear green door.',
            'Locked tripod, no pan or internal cut.',
            '昌叔 leads screen right and down; 陳樂言 follows carrying the jug in his left hand. Both remain visible.',
            [(0,1.5,'Both men briefly pause and listen beside the floor '+str(floor)+' sign.'),(1.5,4,'They resume descending screen right; this is extra source material, not the planned edit.')],
            [jug],[jug],[], 'Soft shoe friction, water drip and air through the vent; no voices.',
            '同構圖中清楚看見不同樓層牌及兩人停耳聽；實際文字可讀性仍待驗。',
            old[0]['beats'][0]['action'],'相同下行方向接不同樓層牌；明示時間省略，並非即時走過三層。')
    at13=[state('c_leyan','position','end of the upper flight on floor 13; behind 昌叔'),jug]
    add(old[0],'stop','先聽見刮擦',4,4,'聲音令下行停住，先建立下方有異常',
        '35mm medium wide; both men and the lower stair opening remain legible.', 'Locked tripod.',
        '昌叔 ahead on the right; 陳樂言 behind on the left; the woman is outside the frame below.',
        [(0,2,'Two scratches come from the floor below. 昌叔 raises his free forearm without changing his grip on the screwdriver.'),(2,4,'陳樂言 stops behind him and listens. Hold the unresolved lower opening.')],
        [jug],at13,[], 'Two dry fingernail scrapes on steel from below; faint vent air.',
        '停步、舉手和指向下層嘅視線；聲源先聞未見。',old[0]['beats'][1]['action'],'離開樓層蒙太奇，停足時間聽清異常。')
    mid=[state('c_leyan','position','midway down from floor 13 to 12; one step behind 昌叔'),jug,
         state('p_knife','status','folded; held by 陳樂言’s right hand inside his right trouser pocket')]
    d=copy.deepcopy(old[1]['dialogue']); d[0]['delivery']='mouths silently'
    reveal=add(old[1],'reveal','熟人的背影 · 保持一鏡',10,10,'先讀樂言辨認反應，再揭示他所望的人',
        '50mm medium close two-shot, gradually panning to the woman on the lower landing.',
        'One continuous tripod pan 20 degrees right from 5 to 8 seconds; no cut, zoom or flashback.',
        '昌叔 foreground left, 陳樂言 just behind him; 黃太 is initially offscreen below right with her back turned.',
        [(0,3,'昌叔 silently mouths the scripted phrase. Both men descend a few steps.'),
         (3,5,'陳樂言 notices the familiar figure below; his brow tightens, his jaw briefly loosens, and his right hand enters his right pocket. Hold on his face for these two seconds.'),
         (5,8,'Pan along his eyeline to 黃太: white nightdress, bare feet, right hand scratching the green steel door; her back remains toward the men.'),
         (8,10,'Hold the woman and stair geography. Her scratching hand stops. Do not insert a generic hand close-up as proof of her identity.')],
        at13,mid,d,'Two fingernail scrapes followed by vent air. The mouthed phrase is inaudible.',
        '樂言面部兩秒反應 → 視線平搖 → 女人背影；只主張樂言認出熟人，未主張觀眾認得姓名。',
        old[1]['action'],'承接舉手；不切走兩秒反應，讓觀眾跟隨樂言視線。')
    notes[reveal['id']]['evidence'].update(goal='named_identity',prior_identity_basis='',status='uncertain')
    notes[reveal['id']]['no_cut_reason']='此處平搖已能依序交代反應與人影；再加反應／手掌特寫會割斷辨認過程。'
    escape=[state('p_buckets','position','on the floor 12 landing'),state('c_leyan','position','floor 13 turn'),jug]
    d=copy.deepcopy(old[2]['dialogue']);d[0]['delivery']='a sudden urgent shout'
    add(old[2],'stone','石粒',8,8,'一聲意外令靜止威脅變成追逐','35mm wide showing the entire stair route.',
        'Hold until the rush; retreat screen left on a stabilizer at 1.2 metres per second for the final two seconds.',
        '黃太 below right; 昌叔 and 陳樂言 above left. Escape travels left and up; the jug stays in 陳樂言’s left hand.',
        [(0,3,'Hold in tense stillness. 黃太 tilts her head left, then right.'),(3,5,'昌叔 steps back onto a small stone. At its click 黃太 turns, exposing bloodshot eyes and cracked lips.'),
         (5,8,'黃太 rushes up toward the men. 昌叔 shouts, drops both buckets on floor 12 and runs up. 陳樂言 reaches the floor 13 turn.')],
        mid,escape,d,'A stone clicks; a constricted nonverbal moan, buckets hit concrete and a rail rattles.',
        '同一全景看清石響、轉頭及逃走方向；轉頭提供外貌，仍不等於觀眾知道姓名。',old[2]['action'],'等足靜止三秒；以石響觸發轉頭，不用額外石粒特寫。')
    injured=[state('p_jug','status','empty; on the floor 13 turn'),state('p_knife','status','open and bloodied; in 陳樂言’s right hand'),
             state('c_wong','status','fallen two steps below the men; still scratching the floor')]
    d=copy.deepcopy(old[3]['dialogue']);d[0]['delivery']='strained urgent cry';d[1]['delivery']='voice breaking in a shout'
    add(old[3],'return','折返',12,12,'用停逃、回望、折返呈現救人的選擇','35mm close medium on 陳樂言, widening by moving back, without changing lens.',
        'Track backward 0.8 metres at 0.1 metres per second; keep the original axis side. One continuous shot.',
        '陳樂言 at the upper-left turn; 昌叔 three steps below right; 黃太 grips 昌叔’s shirt from below. His shoulder masks contact.',
        [(0,3,'昌叔 cries for help. 陳樂言 freezes and holds his reaction for two seconds, looking from the upper exit back to 昌叔.'),
         (3,6,'昌叔 elbows twice without effect and braces her chin with his left hand. 陳樂言 sets the jug on the floor 13 turn, opens his knife with his right hand and returns down right.'),
         (6,9,'His first strike fails. 黃太 screams nonverbally; 昌叔 gives the scripted instruction. Keep contact obscured by 昌叔’s shoulder.'),
         (9,12,'陳樂言 strikes again behind the shoulder occlusion. 昌叔 pushes her away. The two men slump; she falls two steps below and still scratches.')],
        [state('c_leyan','position','floor 13 turn'),jug],injured,d,
        'Strained cries, torn fabric, breathing, a nonverbal scream and body impact on stairs; no exaggerated penetration sound.',
        '樂言望出口再望昌叔、放樽後折返；手同道具位置有可見依據。',old[3]['action'],'切入被呼喚者，保留兩秒決定；救人行動連續完成。')
    dead=[state('p_jug','status','empty; on the floor 13 turn'),state('p_knife','status','open and bloodied; in 陳樂言’s right hand'),
          state('c_wong','status','dead; on the stairs at floor 12')]
    d=copy.deepcopy(old[4]['dialogue'][:2]);d[0]['delivery']='breathy';d[1]['delivery']='without looking at 陳樂言'
    add(old[4],'aftermath','唔再問名字 · 留在樂言',10,10,'留在樂言身上承受後果，讓畫外聲音完成動作',
        '135mm chest-up reaction of 陳樂言 against the grey concrete wall.', 'Locked tripod at seated eye level, no cut.',
        '陳樂言 on the left against the wall; 昌叔 below right, mainly offscreen; green rail soft in the background.',
        [(0,4,'陳樂言 looks at his bloodied right hand and retches. Offscreen 昌叔 ends 黃太’s movement; the scratching stops.'),
         (4,7,'陳樂言 asks the scripted question, then hold two seconds of silence. Do not cut away from his face.'),
         (7,10,'昌叔 answers from offscreen. Hold 陳樂言’s wet eyes, difficult swallow and uncompleted response.')],
        injured,dead,d,'Dry retching, a metal handle gripped, two dull impacts offscreen; scratching ceases. No music.',
        '留住樂言反應；昌叔答案從畫外傳來。停止刮擦是動作結果嘅聲音線索。',old[4]['beats'][0]['action'],
        '此段不切去施襲細節；原作要求留在樂言臉上。')
    d=copy.deepcopy(old[4]['dialogue'][2:]);
    for line,delivery in zip(d,['quietly','with a tight throat']):
        line['start']-=10;line['end']-=10;line['delivery']=delivery
    end=[state('c_wong','status','dead; on the stairs at floor 12'),jug,state('p_buckets','position','held in 昌叔’s left hand'),
         state('p_knife','status','folded; in 陳樂言’s right trouser pocket')]
    add(old[4],'continue','仲落唔落',5,5,'以重新拿起容器及答覆，落實繼續下樓的選擇',
        '35mm wide from the same side, including the floor 12 landing and the upper turn.', 'Locked tripod; no internal cut.',
        'After a clear time ellipsis, 陳樂言 has retrieved the jug in his left hand; 昌叔 reaches for the buckets on floor 12. The knife is folded in the right trouser pocket.',
        [(0,1,'After the indicated ellipsis, hold the recovered jug and 昌叔 lifting both buckets; do not compress walking between floors into this second.'),
         (1,3.5,'昌叔 asks the scripted question. 陳樂言 looks down the stair route, still trembling.'),
         (3.5,5,'陳樂言 answers once. Both settle facing down the stairs, ready to continue screen right.')],
        end,end,d,'Bucket handles lightly knock; strained breathing and vent air.',
        '容器重新在手、望向下行路線及簡短答覆；唔以道具特寫取代人嘅選擇。',old[4]['transition_note'],
        '明示時間省略：拾回十三樓水樽、十二樓水桶及收刀在切點省略；依據原有末段，不為生成錯誤補事件。')
    scene['time_of_day']='Pre-dawn; no electric light.'
    scene['director_plan']={'beats':[dict(id=s['direction']['beat_ids'][0],event=s['shot_purpose'],intent=dict(
        audience_knowledge_before='兩人停電期間帶容器下樓取水；未有觀眾認得黃太面孔的已驗證依據。',
        audience_must_learn=s['shot_purpose'],emotional_target='由戒備、停住，到救人及承受後果。',
        visual_priority=s['direction']['visual_carrier'],reveal_strategy=s['direction']['cut_in_reason'],
        coverage_strategy=notes[s['id']]['no_cut_reason'])) for s in shots],
        'reveal_order':[s['direction']['beat_ids'][0] for s in shots]}
    start=next(i for i,s in enumerate(plan['shots']) if s['scene_id']==sid)
    plan['shots']=plan['shots'][:start]+shots+plan['shots'][start+len(old):]
    old_ids={s['id'] for s in old};index=next(i for i,e in enumerate(plan['edit_plan']) if e['shot_id'] in old_ids)
    outside=[e for e in plan['edit_plan'] if e['shot_id'] not in old_ids]
    plan['edit_plan']=outside[:index]+edits+outside[index:]
    cues=editorial.original_audio(editorial.scope(plan,sid))
    # A deliberate sound bridge precedes the reveal, independent of visual cut timing.
    stop=next(e for e in edits if e['shot_id'].endswith('_stop'))
    cursor=sum(e['planned_edit_out']-e['planned_edit_in'] for e in edits[:edits.index(stop)])
    cues.append(dict(id=prefix+'scratch_bridge',shot_id=stop['shot_id'],source_in=0,source_out=3,
        timeline_in=cursor+2,kind='sound',text='樓下刮鋼門：跨入下一畫面一秒；暫未有音檔。'))
    provenance=dict(author='Codex supervising editor',origin='manually_authored_trial',
        source_revision=p['revision'],source_hash=editorial.basis(p),
        adaptation='選用剪接動機、聲音先行及戲劇視點；固定節奏、固定剪格及上游模型路由均不採作硬規則。',
        prompt_labels={'l_stairs':'residential fire stairwell','p_jug':'five-litre plastic water jug',
        'p_buckets':'two plastic buckets','p_knife':'folding knife','p_driver':'long screwdriver'},
        limitations=['文字卡只能比較次序及暫定時長，未驗證構圖、表演、嘴形或實際聲音。',
        '黃太姓名辨識仍需觀眾先前認識她的依據；此試行不增寫對白或回憶。',
        '實際影片匯入、素材出入點及成片輸出留待素材階段；目前均為預定範圍。'])
    return sid,plan,notes,cues,provenance
