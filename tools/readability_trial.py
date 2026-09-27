"""Render a labelled 480x800 typography trial; no station, GPIO or paid calls.

Run from the repository root with .venv/bin/python tools/readability_trial.py.
This is a comparison specimen, not a proposed complete report layout.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'display'))
from gardenink.render import Page, font, BLACK


def render_trial():
    page = Page()

    def text(x, y, value, size, style='sans'):
        # Fail instead of silently shrinking a specimen under comparison.
        bounds = font(size, style).getbbox(value)
        assert x + bounds[2] - bounds[0] <= 456, (value, size)
        assert y + bounds[3] - bounds[1] <= 780, (value, size)
        page.text((x, y), value, size, style)

    text(24, 20, 'Readability trial', 28, 'serif')
    text(24, 59, 'SAMPLE TEXT · not a live garden report', 13, 'bold')
    text(24, 83, 'Compare A, B and C at your usual distance.', 14)
    text(24, 105, 'Which is easiest to read without leaning in?', 14)

    variants = [
        ('A · Current small-card type', 13, 'serif', 10, 'italic', 10, 'sans'),
        ('B · Larger editorial type', 18, 'serif', 14, 'italic', 14, 'sans'),
        ('C · Larger plain type', 18, 'bold', 14, 'sans', 14, 'sans'),
    ]
    for i, (label, name_size, name_style, latin_size, latin_style, body_size, body_style) in enumerate(variants):
        y = 143 + i * 184
        page.rule(y)
        text(24, y + 14, label, 14, 'bold')
        text(24, y + 45, 'Robin · Treecreeper · Tawny Owl', name_size, name_style)
        text(24, y + 76, 'Erithacus rubecula · Certhia familiaris', latin_size, latin_style)
        text(24, y + 104, 'Heard at 11.57am · 21 detections this hour', body_size, body_style)
        text(24, y + 130, 'Report covers 11.01am to 12.01pm BST', body_size, body_style)
        text(24, y + 156, '+ means at least · Incomplete scan', body_size, body_style)

    page.rule(698)
    text(24, 714, 'Reply: A, B or C; hardest line; viewing distance.', 13)
    text(24, 738, 'Then we will test spacing in the full bird layout.', 13)
    text(24, 762, 'Normal reports resume automatically after the trial.', 12)
    assert page.im.size == (480, 800)
    pixels = page.im.get_flattened_data() if hasattr(page.im, 'get_flattened_data') else page.im.getdata()
    assert set(pixels) == {BLACK, (255, 255, 255)}
    return page.im


if __name__ == '__main__':
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('local/previews/readability-trial.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    render_trial().save(output)
    print(output.resolve())
