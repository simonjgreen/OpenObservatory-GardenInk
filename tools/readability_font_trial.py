"""Offline font x rasterizer specimen; no application/driver changes or GPIO."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'display'))
from PIL import Image, ImageDraw, ImageFont
from gardenink.render import Page, BLACK

FONTS = {
    'DejaVu Sans': Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    'Noto Sans': Path('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'),
}


def specimen_text(page, xy, value, family, mode, size=14):
    face = ImageFont.truetype(str(FONTS[family]), size)
    box = face.getbbox(value)
    # Extra scratch margin avoids clipping alternate monochrome glyph bounds.
    mask = Image.new('L', (450, 60), 0)
    draw = ImageDraw.Draw(mask)
    draw.fontmode = mode
    draw.text((4-box[0], 4-box[1]), value, font=face, fill=255)
    if mode == 'L':
        mask = mask.point(lambda p: 255 if p >= 112 else 0)
    ink = mask.getbbox()
    assert ink and ink[0] > 0 and ink[1] > 0 and ink[2] < 449 and ink[3] < 59
    assert xy[0] + ink[2] - 4 <= 456 and xy[1] + ink[3] - 4 <= 780
    page.im.paste(BLACK, (xy[0]-4, xy[1]-4), mask)


def render_trial():
    page = Page()
    page.text((24, 20), 'Font and stroke trial', 27, 'serif')
    page.text((24, 59), 'SAMPLE · same sizes, regular weight throughout', 13, 'bold')
    page.text((24, 84), 'Compare the strokes, then read at normal distance.', 13)
    variants = (
        ('D', 'DejaVu Sans', 'L', 'current rendering'),
        ('E', 'DejaVu Sans', '1', 'direct monochrome'),
        ('F', 'Noto Sans', 'L', 'current rendering'),
        ('G', 'Noto Sans', '1', 'direct monochrome'),
    )
    for index, (label, family, mode, description) in enumerate(variants):
        y = 112 + index * 149
        page.rule(y)
        page.text((24, y+12), f'{label} · {family} / {description}', 13, 'bold')
        for offset, value, size in (
            (40, 'Robin · Treecreeper · Tawny Owl', 18),
            (67, 'Erithacus rubecula · Certhia familiaris', 14),
            (91, 'Heard at 11.57am · 21 detections this hour', 14),
            (116, 'HHH nnn mmm · Il1 · 0O · 11.01am', 14),
        ):
            specimen_text(page, (24, y+offset), value, family, mode, size)
    page.rule(715)
    page.text((24, 731), 'Which reads best: D, E, F or G?', 15, 'bold')
    page.text((24, 757), 'Compare D/E for rendering; E/G for font choice.', 13)
    pixels = page.im.get_flattened_data() if hasattr(page.im, 'get_flattened_data') else page.im.getdata()
    assert set(pixels) == {BLACK, (255, 255, 255)}
    assert page.im.size == (480, 800)
    return page.im


if __name__ == '__main__':
    path = Path('local/previews/readability-font-trial.png')
    path.parent.mkdir(parents=True, exist_ok=True)
    render_trial().save(path)
    print(path.resolve())
