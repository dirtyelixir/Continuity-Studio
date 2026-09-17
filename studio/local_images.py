"""Pinned local image recipes; selection is structural, never a provider fallback."""
import hashlib
import json
import secrets
from pathlib import Path
from . import store, image_loras

ROOT = Path(__file__).resolve().parent.parent / 'workflows' / 'local-images'
VERSION = 'studio-local-images-v6'
# Stills that condition a shot share the previous square default's pixel budget.
FRAME_MEGAPIXELS = 1.0
PROVIDER = {'id':'comfy_local','name':'本機 ComfyUI · Klein / Krea2','kind':'comfy','model':VERSION,'base_url':'http://127.0.0.1:8188','key_env':'','capabilities':['image']}
OPERATIONS = {'auto':'自動選擇','new':'全新圖片','reference':'參考圖生成／多圖合成','sheet':'角色四視圖','portrait':'人物写真','face_swap':'換臉（來源圖＋身份參考）','edit':'整張修改','inpaint':'指定範圍修改','outpaint':'擴展畫面'}
RECIPES = {
 'krea_new': {'name':'Krea2 Turbo · 文生圖','family':'krea','model':'krea2_turbo_int8_convrot.safetensors','edit':False},
 'krea_edit': {'name':'Krea2 Muse · 單圖編輯','family':'krea','model':'Muse by Stable Yogi Krea2 V2.5 Extended INT8-ConvRot C79.safetensors','edit':True},
 'krea_two': {'name':'Krea2 Turbo · 雙圖編輯','family':'krea','model':'krea2_turbo_int8_convrot.safetensors','edit':True},
 'krea_inpaint': {'name':'Krea2 Turbo · 範圍修改','family':'krea','model':'krea2_turbo_int8_convrot.safetensors','edit':True},
 'krea_outpaint': {'name':'Krea2 Turbo · 擴圖','family':'krea','model':'krea2_turbo_int8_convrot.safetensors','edit':True},
 'klein_reference': {'name':'Klein True V3 · 多圖參考','family':'klein'},
 'klein_sheet': {'name':'Klein True V3 · 四視圖','family':'klein'},
 'klein_portrait': {'name':'Klein True V3 · 写真','family':'klein'},
 'klein_face': {'name':'Klein True V3 · 換臉','family':'klein'},
}

def origins():
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'original').glob('*.json'))}


def select(inp, operation='auto', region=None, padding=None):
    if operation not in OPERATIONS: raise ValueError('未知本機圖片工作方式。')
    kind=inp['image_source']['target_kind']; count=len(inp['images'])
    source=bool(inp.get('source_asset_id'))
    if count>8: raise ValueError('本機參考生成目前最多 8 張輸入（含排版）；不會丟棄圖片。')
    if kind=='character' and operation not in ('auto','sheet','edit','face_swap','inpaint','outpaint'):
        raise ValueError('角色資產必須交付四視圖；写真／換臉請用相應鏡頭或其他圖片目標。')
    if operation in ('edit','inpaint','outpaint','face_swap') and not source:
        raise ValueError('此修改方式需要先從圖片版本選「修訂」，指定來源圖片。')
    if operation=='new' and count: raise ValueError('全新文生圖不能忽略已選參考；請用自動或參考圖生成。')
    if operation in ('inpaint','outpaint') and count!=1:
        raise ValueError('範圍修改／擴圖需要且只能有來源圖一張；請取消額外參考。角色排版參考亦計入。')
    if operation=='reference' and not count: raise ValueError('參考生成需要至少一張參考圖片。')
    if operation=='sheet' and kind!='character': raise ValueError('四視圖工作方式只適用於角色資產。')
    if operation=='face_swap':
        identity=[r for r in inp.get('input_references',[]) if r.get('purpose')=='identity']
        expected=3 if inp.get('layout_reference') else 2
        if count!=expected or len(identity)!=1: raise ValueError('換臉需要來源圖與一張已選身份參考（角色可另附排版圖）。')
    if operation=='inpaint':
        if not region or len(region)!=4 or any(type(x) is not int for x in region): raise ValueError('請填寫範圍 x、y、寬、高（百分比整數）。')
        x,y,w,h=region
        if min(x,y)<0 or min(w,h)<=0 or x+w>100 or y+h>100: raise ValueError('修改範圍必須位於圖片內。')
    if operation=='outpaint':
        if not padding or len(padding)!=4 or any(type(x) is not int or x<0 or x>512 or x%8 for x in padding) or not any(padding): raise ValueError('擴圖需填左、上、右、下像素，0–512，8 的倍數，至少一邊大於 0。')
    if operation in ('inpaint','outpaint'): recipe='krea_'+operation
    elif operation=='face_swap': recipe='klein_face'
    elif kind=='character' or operation=='sheet': recipe='klein_sheet'
    elif operation=='portrait': recipe='klein_portrait'
    elif not count: recipe='krea_new'
    elif count<=2 and operation!='reference' and (source or count==1): recipe='krea_edit' if count==1 else 'krea_two'
    else: recipe='klein_reference'
    # Canonical roles retain their numbered order. Krea source must be first;
    # reordered transport would change its trained scene/subject semantics.
    if recipe.startswith('krea_') and source and 'EDIT TARGET' not in inp['image_reference_roles'][0]:
        if operation in ('inpaint','outpaint'): raise ValueError('來源圖必須是唯一輸入。')
        recipe='klein_reference'
    width,height=(2048,1152) if recipe=='klein_sheet' else (1536,1024) if kind=='character' else (1024,1024)
    if kind=='frame':
        # A frame conditions a shot that is rendered at the Studio video aspect, so the
        # still canvas must carry that same aspect instead of defaulting to a square.
        # A square first frame cannot express the wide placement the shot direction asks
        # for (subject screen-left, Pip screen-right, prop large in the lower foreground),
        # and it would not match the aspect the video is rendered at. Keep the previous
        # still megapixel budget and correct only the ratio.
        from . import h3_render_settings as render_settings
        width,height=render_settings.dimensions(render_settings.defaults()['aspect_ratio'],FRAME_MEGAPIXELS)
    if source and recipe.startswith('krea_'):
        from PIL import Image
        with Image.open(inp['images'][0]) as im:
            ratio=im.width/im.height
        width=max(256,round((1048576*ratio)**.5/32)*32);height=max(256,round(width/ratio/32)*32)
        if width*height>2097152 or max(width,height)>2048: raise ValueError('來源圖比例過長；請先準備合適構圖。')
    if padding and recipe=='krea_outpaint' and (width+padding[0]+padding[2])*(height+padding[1]+padding[3])>2097152: raise ValueError('擴圖輸出不能超過 2MP，請減少邊距。')
    return {'version':VERSION,'operation':operation,'recipe':recipe,'name':RECIPES[recipe]['name'],'reason':f'{kind}；{count} 張完整輸入；'+('指定 '+OPERATIONS[operation] if operation!='auto' else '按目標與參考數選擇'), 'reference_count':count,'width':width,'height':height,'region':region if operation=='inpaint' else None,'padding':padding if operation=='outpaint' else None,'seed':secrets.randbelow(2**53),'origins':origins()}


def build(plan, prompt, images, prefix):
    """Build only the selected branch. No sample prompts, external LLMs or previews."""
    image_loras.validate_frozen(plan)
    if plan['recipe']=='klein_sheet': return build_sheet(plan,prompt,images,prefix)
    prompt=image_loras.prompt_with_triggers(plan,prompt)
    recipe=RECIPES[plan['recipe']]; g={}
    def node(name,typ,**inputs):
        g[name]={'class_type':typ,'inputs':inputs}; return [name,0]
    def creative(model):
        for i,row in enumerate(plan.get('creative_loras',[])):
            model=node('creative_lora_'+str(i),'LoraLoaderModelOnly',model=model,lora_name=row['name'],strength_model=row['strength'])
        return model
    w,h=plan['width'],plan['height']; seed=plan['seed']
    klein=recipe['family']=='klein'
    model=node('model','UNETLoader',unet_name='Flux2-Klein-9B-True-V3-bf16.safetensors' if klein else recipe['model'],weight_dtype='default')
    clip=node('clip','CLIPLoader',clip_name='qwen3_8b_abliterated_v2-fp8mixed.safetensors' if klein else 'qwen3vl_4b_fp8_scaled.safetensors',type='flux2' if klein else 'krea2',device='default')
    vae=node('vae','VAELoader',vae_name='flux2-vae.safetensors' if klein else 'qwen_image_vae.safetensors')
    refs=[node('input_'+str(i),'LoadImage',image=name) for i,name in enumerate(images)]
    mask=base=None
    if plan['recipe'] in ('krea_inpaint','krea_outpaint'):
        base=node('base','ImageScale',image=refs[0],upscale_method='lanczos',width=w,height=h,crop='disabled')
        if plan['recipe']=='krea_outpaint':
            l,t,r,b=plan['padding']; base=node('pad','ImagePadForOutpaint',image=base,left=l,top=t,right=r,bottom=b,feathering=0);mask=['pad',1];w+=l+r;h+=t+b
        else:
            x,y,rw,rh=plan['region'];x=int(w*x/100);y=int(h*y/100);rw=max(1,int(w*rw/100));rh=max(1,int(h*rh/100))
            empty=node('mask_empty','SolidMask',value=0.0,width=w,height=h)
            patch=node('mask_patch','SolidMask',value=1.0,width=rw,height=rh)
            mask=node('mask','MaskComposite',destination=empty,source=patch,x=x,y=y,operation='add')
        refs[0]=node('marked','DrawMaskOnImage',image=base,mask=mask,color='0, 0, 255',device='cpu')
    latent=node('latent','EmptyFlux2LatentImage' if klein else 'EmptySD3LatentImage',width=w,height=h,batch_size=1)
    if klein:
        model=node('turbo','LoraLoaderModelOnly',model=model,lora_name='klein_9B_Turbo_r128.safetensors',strength_model=0.2)
        if plan['recipe']=='klein_face': model=node('face_lora','LoraLoaderModelOnly',model=model,lora_name='bfs_head_v1_flux-klein_9b_step3500_rank128.safetensors',strength_model=0.75)
        model=creative(model)
        model=node('attention','ModelAttentionBackend',model=model,attention='comfy kitchen attention')
        positive=node('positive','CLIPTextEncode',clip=clip,text=prompt);negative=node('negative','ConditioningZeroOut',conditioning=positive)
        for i,ref in enumerate(refs):
            scaled=node(f'scale_{i}','ImageScaleToTotalPixels',image=ref,upscale_method='lanczos',megapixels=1.0,resolution_steps=1)
            encoded=node(f'encode_{i}','VAEEncode',pixels=scaled,vae=vae)
            positive=node(f'positive_ref_{i}','ReferenceLatent',conditioning=positive,latent=encoded)
            negative=node(f'negative_ref_{i}','ReferenceLatent',conditioning=negative,latent=encoded)
        noise=node('noise','RandomNoise',noise_seed=seed); guider=node('guider','CFGGuider',model=model,positive=positive,negative=negative,cfg=1.0)
        sampler=node('sampler','KSamplerSelect',sampler_name='euler');sigmas=node('sigmas','Flux2Scheduler',steps=8,width=w,height=h)
        samples=node('samples','SamplerCustomAdvanced',noise=noise,guider=guider,sampler=sampler,sigmas=sigmas,latent_image=latent)
    else:
        if recipe['edit']:
            if not 1<=len(refs)<=2: raise ValueError('Krea 編輯只能接收一或兩張圖片。')
            model=node('edit_lora','LoraLoaderModelOnly',model=model,lora_name='Flux Krea 2/krea2_identity_edit_v1_2.safetensors',strength_model=1.0)
            model=creative(model)
            encoded=[node(f'encode_{i}','VAEEncode',pixels=ref,vae=vae) for i,ref in enumerate(refs)]
            extra={'source_latent_b':encoded[1],'source_image_b':refs[1]} if len(refs)==2 else {}
            model=node('edit_patch','Krea2EditModelPatch',model=model,source_latent=encoded[0],vae=vae,source_image=refs[0],target_latent=latent,ref_boost=4.0,ref_boost_a=1.0,fit_mode='fit',**extra)
            imgs={'image':refs[0],**({'image_b':refs[1]} if len(refs)==2 else {})}
            positive=node('positive','Krea2EditGroundedEncode',clip=clip,prompt=prompt,grounding_px=768,system_prompt='',**imgs)
            negative=node('negative','Krea2EditGroundedEncode',clip=clip,prompt='',grounding_px=768,system_prompt='',**imgs)
        else:
            if refs: raise ValueError('文生圖不可丟棄參考。')
            model=creative(model)
            positive=node('positive','CLIPTextEncode',clip=clip,text=prompt);negative=node('negative','ConditioningZeroOut',conditioning=positive)
        samples=node('samples','KSampler',model=model,positive=positive,negative=negative,latent_image=latent,seed=seed,steps=10,cfg=1.0,sampler_name='euler',scheduler='simple',denoise=1.0)
    image=node('decoded','VAEDecode',samples=samples,vae=vae)
    if mask: image=node('composite','ImageCompositeMasked',destination=base,source=image,x=0,y=0,resize_source=False,mask=mask)
    node('save','SaveImage',images=image,filename_prefix=prefix)
    return g


def validate_graph(graph, info):
    missing=[]
    for name,node in graph.items():
        schema=info.get(node['class_type'])
        if not schema: missing.append(node['class_type']);continue
        fields={**schema['input'].get('required',{}),**schema['input'].get('optional',{})}
        for key in schema['input'].get('required',{}):
            if key not in node['inputs']: missing.append(name+'.'+key)
        for key,value in node['inputs'].items():
            if key not in fields: missing.append(name+'.'+key+' unsupported');continue
            spec=fields[key]
            if isinstance(value,list) and len(value)==2 and isinstance(value[0],str) and isinstance(value[1],int):
                if value[0] not in graph:missing.append('broken link '+name+'.'+key)
            elif node['class_type']=='LoadImage' and key=='image': pass # uploaded after readiness check
            elif isinstance(spec[0],list) and value not in spec[0]: missing.append(str(value))
    if missing: raise ValueError('本機工作流缺少／不相容依賴：'+'、'.join(missing))


def build_sheet(plan, prompt, images, prefix):
    """Four separately conditioned views assembled into one canonical candidate."""
    # The shared brief remains recorded verbatim in render-prompt.txt; per-panel
    # text is additionally frozen in comfy-graph.json. Replace only composition.
    fields=('Visual style:','Appearance:','Lighting:','Requested changes:',
            'Reference images:','Design priority:','High reference preservation:')
    sections=[s for s in prompt.split('\n\n') if s.startswith(fields)]
    design='\n\n'.join(sections) if sections else prompt
    views=[
        'FRONT-FACING FULL BODY VIEW. Face, chest and toes face the camera. Show entire head to shoes in a natural standing pose. Head top at about 10 percent of canvas height and soles at about 92 percent. No cropped feet.',
        'LEFT-FACING FULL BODY PROFILE. Nose points toward the LEFT BORDER, body in strict 90 degree side profile. Show entire head to shoes in the same standing pose and body scale as the front view. Match its head height and foot baseline.',
        'FULL BODY REAR VIEW. Back of head and body face camera, face invisible. Show entire head to shoes in the same standing pose and body scale as the front view. Match its head height and foot baseline.',
        'ENLARGED FRONT-FACING FACE CLOSE-UP. Face looking straight at camera. Frame from the complete hair/top of head down to shoulders and upper chest only. Facial details large and clear; no waist, legs or full body.'
    ]
    body_width=(int(plan['width']*0.21875)//32)*32
    portrait_width=plan['width']-3*body_width
    graph={};outputs=[]
    for i,view in enumerate(views):
        panel_prompt=('Render exactly ONE person in ONE view. This is one panel of a sheet that software assembles later. Never render panels, borders, collages or multiple views. Layout reference images are examples only; ignore their multi-view layout for this panel.\n\n'+design+'\n\nMANDATORY CAMERA FOR THIS PANEL: '+view+' Same identity, proportions, hair and wardrobe in all views. Plain white studio background. No text.')
        if i:panel_prompt+=' The final reference image is the front full-body view just rendered for this same candidate. Preserve its identity, exact wardrobe, accessories, proportions and held objects. Follow this panel camera and framing; only the last face panel is enlarged.'
        sub=build({**plan,'recipe':'klein_reference','width':portrait_width if i==3 else body_width,'height':plan['height'],'seed':(plan['seed']+i)%2**53},panel_prompt,images,prefix)
        sub.pop('save')
        sub['sigmas']['inputs']['steps']=16
        if i:
            sub['portrait_encode']={'class_type':'VAEEncode','inputs':{'pixels':['__portrait__',0],'vae':['vae',0]}}
            for direction in ('positive','negative'):
                old=sub['guider']['inputs'][direction]
                key=direction+'_portrait';sub[key]={'class_type':'ReferenceLatent','inputs':{'conditioning':old,'latent':['portrait_encode',0]}}
                sub['guider']['inputs'][direction]=[key,0]
        for key,value in sub.items():
            value['inputs']={k:([('p0_decoded' if v[0]=='__portrait__' else f'p{i}_'+v[0]),v[1]] if isinstance(v,list) and len(v)==2 and isinstance(v[0],str) and isinstance(v[1],int) else v) for k,v in value['inputs'].items()}
            graph[f'p{i}_'+key]=value
        outputs.append([f'p{i}_decoded',0])
    combined=outputs[0]
    for i,output in enumerate(outputs[1:],1):
        name='join'+str(i);graph[name]={'class_type':'ImageConcanate','inputs':{'image1':combined,'image2':output,'direction':'right','match_image_size':False}};combined=[name,0]
    graph['save']={'class_type':'SaveImage','inputs':{'images':combined,'filename_prefix':prefix}}
    return graph
