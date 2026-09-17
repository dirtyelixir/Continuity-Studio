import os
import pytest
from PIL import Image
from studio import image_output_quality as quality


def make_image(tmp_path, name, color=None, size=(8, 8), mode='RGB', pixel_fn=None):
    path = tmp_path / name
    if pixel_fn:
        im = Image.new(mode, size)
        for y in range(size[1]):
            for x in range(size[0]):
                im.putpixel((x, y), pixel_fn(x, y))
    else:
        im = Image.new(mode, size, color)
    im.save(path, format='PNG')
    return path


@pytest.fixture(autouse=True)
def clean_cache():
    quality.clear_cache()
    yield
    quality.clear_cache()


def test_all_black_rgb_is_invalid(tmp_path):
    path = make_image(tmp_path, 'black.png', (0, 0, 0))
    r = quality.inspect_image(str(path))
    assert r == {'valid': False, 'code': 'full_black', 'message': '圖片全黑（所有像素均為純黑 RGB）。', 'width': 8, 'height': 8}


def test_all_white_rgb_is_invalid(tmp_path):
    path = make_image(tmp_path, 'white.png', (255, 255, 255))
    r = quality.inspect_image(str(path))
    assert r == {'valid': False, 'code': 'full_white', 'message': '圖片全白（所有像素均為純白 RGB）。', 'width': 8, 'height': 8}


def test_fully_transparent_is_invalid(tmp_path):
    path = make_image(tmp_path, 'transparent.png', (120, 60, 30, 0), mode='RGBA')
    r = quality.inspect_image(str(path))
    assert r == {'valid': False, 'code': 'fully_transparent', 'message': '圖片完全透明（沒有不透明像素）。', 'width': 8, 'height': 8}


def test_unreadable_file_is_invalid(tmp_path):
    path = tmp_path / 'broken.png'
    path.write_bytes(b'not really an image')
    r = quality.inspect_image(str(path))
    assert r == {'valid': False, 'code': 'unreadable', 'message': '圖片檔案無法讀取。', 'width': 0, 'height': 0}


def test_texture_dark_valid(tmp_path):
    # Low-light image with nonconstant content: base near-black plus visible detail.
    path = make_image(tmp_path, 'dark_texture.png', pixel_fn=lambda x, y: (8, 8, 10) if (x + y) % 2 == 0 else (30, 30, 38))
    r = quality.inspect_image(str(path))
    assert r['valid'] is True
    assert r['code'] == 'valid'
    assert r['message'] == '圖片內容正常。'
    assert r['width'] == 8 and r['height'] == 8


def test_uniform_non_black_white_passes(tmp_path):
    # Arbitrary uniform swatch: must pass, no creative judgement.
    path = make_image(tmp_path, 'solid_blue.png', (0, 0, 255))
    r = quality.inspect_image(str(path))
    assert r['valid'] is True
    assert r['code'] == 'valid'


def test_opaque_content_despite_alpha(tmp_path):
    # RGBA image with full alpha everywhere: content counts, alpha presence alone does not disqualify.
    path = make_image(tmp_path, 'opaque.png', (120, 60, 30, 255), mode='RGBA')
    r = quality.inspect_image(str(path))
    assert r['valid'] is True
    assert r['code'] == 'valid'


def test_stale_cache_invalidates(tmp_path):
    path = make_image(tmp_path, 'cache.png', (0, 0, 0))
    first = quality.inspect_image(str(path))
    assert first['valid'] is False and first['code'] == 'full_black'
    # Overwrite in place with valid content; the same resolved path must re-read.
    path2 = make_image(tmp_path, 'cache_valid.png', (100, 50, 200))
    path2.replace(path)
    second = quality.inspect_image(str(path))
    assert second['valid'] is True
    assert second['code'] == 'valid'
    # And re-inspecting the now-deleted path reports unreadable, not a stale cache hit.
    os.remove(path)
    assert quality.inspect_image(str(path))['code'] == 'unreadable'


def test_require_image_raises_on_invalid(tmp_path):
    path = make_image(tmp_path, 'black2.png', (0, 0, 0))
    with pytest.raises(ValueError, match='圖片全黑'):
        quality.require_image(str(path))


def test_require_image_returns_valid(tmp_path):
    path = make_image(tmp_path, 'green.png', (0, 200, 0))
    r = quality.require_image(str(path))
    assert r['valid'] is True and r['code'] == 'valid'


@pytest.mark.parametrize('mode,color,code',[('L',0,'full_black'),('L',255,'full_white'),('P',0,'full_black')])
def test_non_rgb_blank_pixels(tmp_path,mode,color,code):
    path=make_image(tmp_path,'converted.png',color,mode=mode)
    assert quality.inspect_image(path)['code']==code


def test_truncated_image_is_unreadable(tmp_path):
    path=make_image(tmp_path,'truncated.png',(120,60,30),size=(256,256))
    path.write_bytes(path.read_bytes()[:70])
    assert quality.inspect_image(path)['code']=='unreadable'


def test_pictureless_noise_is_invalid(tmp_path):
    """A decoded render with no picture in it is unusable even when no pixel is all-black.

    Calibrated against a real corrupt render (spread 18.1 / detail 19.6) versus eleven
    genuine generated keyframes and references (spread 118-175 / detail 6.3-12.0).
    """
    size=(256,256)
    def noise(x,y):
        n=(x*1103515245+y*12345)%97
        return (90+n%40,80+n%35,70+n%30)
    path=make_image(tmp_path,'noise.png',size=size,pixel_fn=noise)
    r=quality.inspect_image(path)
    assert r['valid'] is False and r['code']=='noise'
    assert r['message']=='圖片是雜訊，沒有可辨識內容（解碼失敗）；請重新生成。'
    assert (r['width'],r['height'])==size
    with pytest.raises(ValueError,match='雜訊'):
        quality.require_image(path)


def test_low_contrast_and_uniform_stills_keep_their_valid_verdict(tmp_path):
    """Only the noise signature is flagged: soft or uniform frames add no creative judgement."""
    # A soft, low-contrast but genuinely graded picture.
    soft=make_image(tmp_path,'soft.png',size=(256,256),pixel_fn=lambda x,y:(100+x//8,98+y//8,96+x//16))
    assert quality.inspect_image(soft)['valid'] is True
    # A uniform swatch stays valid exactly as before.
    for color,name in (((0,200,0),'green.png'),((0,0,255),'blue.png'),((40,40,45),'dark_solid.png')):
        assert quality.inspect_image(make_image(tmp_path,name,color,size=(256,256)))['valid'] is True


def test_small_tiny_tiles_are_exempt_from_the_structure_probe(tmp_path):
    """The coarse-grid probe needs an image larger than its grid; tiny fixtures keep their rule."""
    path=make_image(tmp_path,'tiny.png',size=(8,8),pixel_fn=lambda x,y:(8,8,10) if (x+y)%2==0 else (30,30,38))
    assert quality.inspect_image(path)['valid'] is True
    assert quality.MIN_STRUCTURE_SIDE>8
