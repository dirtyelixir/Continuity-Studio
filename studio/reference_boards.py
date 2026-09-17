"""Lossless transport boards for image tools with five input slots.

Original canon/assets stay separate; this only packages copied job inputs.
"""
import json,math
from pathlib import Path
from PIL import Image,ImageDraw


def prepare(images,work,limit=5):
    images=[Path(p).resolve() for p in images]
    if len(images)<=limit:return images,[],''
    # Keep the leading identity/location inputs independent. Every remaining
    # original is pasted at native resolution, with a separate numbered gutter.
    retained=images[:limit-1];packed=images[limit-1:];opened=[]
    try:
        for path in packed:
            with Image.open(path) as im:opened.append(im.convert('RGB'))
        cols=math.ceil(math.sqrt(len(opened)));rows=math.ceil(len(opened)/cols)
        width=max(im.width for im in opened);height=max(im.height for im in opened);gutter=48
        board=Image.new('RGB',(cols*width,rows*(height+gutter)),(240,240,240));draw=ImageDraw.Draw(board);tiles=[]
        for i,(path,im) in enumerate(zip(packed,opened)):
            x=(i%cols)*width;y=(i//cols)*(height+gutter);number=limit+i
            draw.text((x+12,y+10),f'Image {number}',fill=(20,20,20),font_size=24)
            board.paste(im,(x,y+gutter));tiles.append({'image_number':number,'source':str(path),'box':[x,y+gutter,x+im.width,y+gutter+im.height]})
        target=(work/'reference-board.png').resolve();board.save(target)
        mapping={'inputs':[str(p) for p in retained]+[str(target)],'board':str(target),'tiles':tiles,'original_count':len(images)}
        (work/'reference-transport.json').write_text(json.dumps(mapping,indent=2))
    finally:
        for im in opened:im.close()
    note=transport_note(len(images),limit)
    return retained+[target],[target],note


def transport_note(count,limit=5):
    if count<=limit:return ''
    return 'The last tool input is a transport reference board, not a scene or storyboard. Its separately labelled tiles are the unchanged originals '+', '.join('Image '+str(i) for i in range(limit,count+1))+'. Match each tile to that numbered image role in the request. Earlier tool inputs match Images 1 through '+str(limit-1)+'. Use every original identity/design; never reproduce the board, labels, gutters, separate panels or incidental prop backgrounds in the generated frame.'
