from __future__ import annotations
from PIL import Image

# Index order is intentionally distinct from the panel's nibble codes.
COLOURS = [(0,0,0), (255,255,255), (255,255,0), (255,0,0), (0,0,255), (0,255,0)]
CODES = (0, 1, 2, 3, 5, 6)  # 4 is not an orange on this six-colour (E) panel.
RESAMPLE = getattr(Image, 'Resampling', Image)
DITHER = getattr(Image, 'Dither', Image)


def quantise(image: Image.Image, dither=True) -> Image.Image:
    pal = Image.new('P', (1,1))
    pal.putpalette(sum((list(c) for c in COLOURS), []) + [255,255,255] * 250)
    out = image.convert('RGB').quantize(palette=pal,
                                      dither=DITHER.FLOYDSTEINBERG if dither else DITHER.NONE)
    # Pillow is allowed to choose a duplicate padding-white index. Canonicalise it.
    return out.point(list(range(6)) + [1]*250)


def pack(image: Image.Image, rotation: int = 90) -> bytes:
    if image.size != (480,800): raise ValueError('Expected 480×800 portrait image')
    if rotation not in (90,270): raise ValueError('Rotation must be 90 or 270')
    panel = image.rotate(rotation, expand=True)
    raw = quantise(panel, dither=False).tobytes()
    codes = bytes(CODES[b] for b in raw)
    return bytes((codes[i] << 4) | codes[i+1] for i in range(0,len(codes),2))
