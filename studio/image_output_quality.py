"""Deterministic blank-output guard for generated images; Pillow only, no provider or GPU calls."""
import os
import threading
from functools import lru_cache
from PIL import Image

# Exact values only: no near-black thresholds or creative judgement.
BLACK=0
WHITE=255

# A decoded render can fail while its pixels are neither all-black nor all-white: uniform
# noise decodes to a picture-less field. Measured on this machine's real outputs, one
# corrupt brown-noise render scored spread 18.1 / detail 19.6 while eleven genuine
# generated keyframes and reference images scored spread 118-175 / detail 6.3-12.0.
# Only the noise signature is flagged -- absent large-scale structure TOGETHER with strong
# local variation. That is deliberately narrower than "low contrast": a uniform swatch and
# a merely soft frame keep their previous valid verdict, so this adds no creative judgement.
STRUCTURE_FLOOR=64
NOISE_DETAIL=14
_STRUCTURE_GRID=8
# The coarse grid needs an image meaningfully larger than itself to mean anything; every
# real render on this machine is at least 768px on its short side.
MIN_STRUCTURE_SIDE=64

_CACHE_MAX=256
_CACHE_LOCK=threading.Lock()


def _cache_key(path):
    """Resolved path plus size and mtime_ns for normal file-change invalidation."""
    resolved=os.path.realpath(path)
    stat=os.stat(resolved)
    return resolved,stat.st_size,stat.st_mtime_ns


def _result(code, message, width, height, valid):
    return {'valid':valid,'code':code,'message':message,'width':width,'height':height}


def _structure(rgb, width, height):
    """Luminance spread across a coarse grid, plus finer local variation.

    Real scenes vary strongly between their darkest and brightest regions, so a small
    grid keeps a wide luminance range. Uniform noise averages to a near-flat grid while
    still differing sharply pixel-to-pixel.
    """
    grid=rgb.resize((_STRUCTURE_GRID,_STRUCTURE_GRID),Image.BOX)
    luminance=[0.299*p[0]+0.587*p[1]+0.114*p[2] for p in grid.get_flattened_data()]
    spread=max(luminance)-min(luminance)
    probe_w=min(256,width)
    probe=rgb.resize((probe_w,max(1,round(probe_w*height/width))),Image.BOX)
    pixels=list(probe.get_flattened_data())
    diffs=[abs(pixels[i][0]-pixels[i-1][0]) for i in range(1,len(pixels)) if i%probe_w]
    detail=sum(diffs)/len(diffs)
    return spread,detail


def _inspect_uncached(path):
    try:
        with Image.open(path) as im:
            width,height=im.size
            im.load()
            # Normalize palette/grayscale images and palette transparency too.
            rgba=im.convert('RGBA')
            extrema=dict(zip(rgba.getbands(),rgba.getextrema()))
    except (OSError,ValueError):
        return _result('unreadable','圖片檔案無法讀取。',0,0,False)

    # Fully transparent: alpha channel exists and no pixel has any alpha at all.
    alpha=extrema.get('A')
    if alpha is not None and alpha[1]==0:
        return _result('fully_transparent','圖片完全透明（沒有不透明像素）。',width,height,False)
    # Exactly all-black or all-white RGB: every channel constant at the exact value.
    rgb=[extrema[band] for band in ('R','G','B') if band in extrema]
    if rgb:
        if all(low==BLACK and high==BLACK for low,high in rgb):
            return _result('full_black','圖片全黑（所有像素均為純黑 RGB）。',width,height,False)
        if all(low==WHITE and high==WHITE for low,high in rgb):
            return _result('full_white','圖片全白（所有像素均為純白 RGB）。',width,height,False)
    # Signal-less decode: not blank by exact value, but a noise field with no picture in it.
    if min(width,height)>=MIN_STRUCTURE_SIDE:
        try:
            spread,detail=_structure(Image.open(path).convert('RGB'),width,height)
        except (OSError,ValueError):
            return _result('unreadable','圖片檔案無法讀取。',0,0,False)
        if spread<STRUCTURE_FLOOR and detail>=NOISE_DETAIL:
            return _result('noise','圖片是雜訊，沒有可辨識內容（解碼失敗）；請重新生成。',width,height,False)
    return _result('valid','圖片內容正常。',width,height,True)


@lru_cache(maxsize=_CACHE_MAX)
def _cached(key):
    return _inspect_uncached(key[0])


def inspect_image(path, use_cache=True):
    """Inspect one image file without mutating it. Returns {valid, code, message, width, height}."""
    if not use_cache:
        return _inspect_uncached(path)
    with _CACHE_LOCK:
        try:
            return _cached(_cache_key(path))
        except OSError:
            return _result('unreadable','圖片檔案無法讀取。',0,0,False)


def clear_cache():
    with _CACHE_LOCK:
        _cached.cache_clear()


def require_image(path):
    """Return the inspection result, or raise ValueError carrying the Traditional Chinese message."""
    result=inspect_image(path)
    if not result['valid']:
        raise ValueError(result['message'])
    return result
