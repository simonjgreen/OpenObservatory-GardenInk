#!/usr/bin/env python3
"""One-reference, one-bird-at-a-time artwork production. Python 3.9+, Pillow.

No API request is sent by plan/review/approve/export. Generate is the only paid
operation, explicitly confirmed. No background work or automatic POST retries.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import datetime as dt
import fcntl
import getpass
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'reference' / 'robin.png'
ENDPOINT = 'https://api.openai.com/v1/images/edits'
DEFAULT_MODEL = 'gpt-image-2-2026-04-21'
RESAMPLE = getattr(Image, 'Resampling', Image).LANCZOS
DITHER = getattr(Image, 'Dither', Image).FLOYDSTEINBERG
ROBIN = 'erithacus_rubecula'
API_RESPONSE_LIMIT = 40 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def write_json(path: Path, data) -> None:
    atomic(path, (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode())


def catalogue():
    items = json.loads((ROOT / 'species.json').read_text(encoding='utf-8'))
    seen = set()
    for item in items:
        slug = item['slug']
        if not re.fullmatch('[a-z]+(?:_[a-z]+)+', slug) or slug in seen:
            raise ValueError('Invalid or duplicate catalogue slug: ' + slug)
        seen.add(slug)
    return items


def select(items, which='all', names=None):
    if names:
        chosen = []
        for name in names:
            key = name.casefold().replace('_', ' ').strip()
            matches = [x for x in items if key in {
                x['slug'].replace('_', ' '), x['scientific_name'].casefold(),
                x['display_name'].casefold(), x['api_label'].casefold(),
                *[s.casefold() for s in x['scientific_aliases']]}]
            if len(matches) != 1: raise ValueError('Species not found or ambiguous: ' + name)
            if matches[0] not in chosen: chosen.append(matches[0])
        return chosen
    if which == 'proof': return [x for x in items if x['proof']]
    if which == 'missing': return [x for x in items if x['source'] == 'terminal_missing']
    return items


@contextlib.contextmanager
def locked(out):
    out.mkdir(parents=True, exist_ok=True)
    with (out / '.studio.lock').open('a') as stream:
        try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('Another artwork operation owns this output folder.')
        yield


def load_state(out):
    p = out / 'state.json'
    value = json.loads(p.read_text()) if p.exists() else {'version': 1, 'birds': {}}
    if value.get('version') != 1 or not isinstance(value.get('birds'), dict):
        raise ValueError('Unrecognised state file; refusing to discard generation history.')
    return value


def save_state(out, state):
    write_json(out / 'state.json', state)


def seed_reference(out, state):
    """Keep the approved original byte-for-byte; never generate a new robin."""
    raw = REFERENCE.read_bytes()
    path = out / 'prepared' / (ROBIN + '.png')
    atomic(path, raw)
    state['birds'][ROBIN] = {
        'status': 'approved', 'sha256': digest(raw), 'reference': True,
        'approved_at': now(), 'file': 'prepared/' + ROBIN + '.png',
        'fingerprint': digest(raw), 'warnings': []}
    save_state(out, state)


def prompt_for(item):
    # Edit STYLE_BRIEF.txt once before the proof stage; do not chain birds as references.
    return (ROOT / 'STYLE_BRIEF.txt').read_text(encoding='utf-8').format(
        api_label=item['api_label'], scientific_name=item['scientific_name'],
        pose=item['pose'], note=item.get('note') or 'Use a representative adult. Do not infer the recorded individual\'s sex, age or seasonal plumage.')


def request_fields(item, args):
    # GPT Image 2 always uses high-fidelity input: omit input_fidelity.
    return {'model': args.model, 'prompt': prompt_for(item), 'n': '1',
            'size': args.size, 'quality': args.quality,
            'background': 'opaque', 'output_format': 'png'}


def fingerprint(item, args):
    return digest(json.dumps({'fields': request_fields(item, args),
                              'reference_sha256': digest(REFERENCE.read_bytes()),
                              'normalisation': 1}, sort_keys=True).encode())


def multipart(fields, image):
    boundary = 'gardenink-' + uuid.uuid4().hex
    body = bytearray()
    for key, value in fields.items():
        body.extend(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + key + '"\r\n\r\n').encode())
        body.extend(str(value).encode())
        body.extend(b'\r\n')
    body.extend(('--' + boundary + '\r\nContent-Disposition: form-data; name="image[]"; filename="robin.png"\r\nContent-Type: image/png\r\n\r\n').encode())
    body.extend(image)
    body.extend(('\r\n--' + boundary + '--\r\n').encode())
    return bytes(body), 'multipart/form-data; boundary=' + boundary


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward an Authorization header to a redirect.


class ApiFailure(RuntimeError):
    def __init__(self, message, uncertain=True):
        super().__init__(message)
        self.uncertain = uncertain


def api_edit(fields, key, timeout=600):
    data, content_type = multipart(fields, REFERENCE.read_bytes())
    request = urllib.request.Request(ENDPOINT, data=data, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': content_type,
        'Accept': 'application/json', 'User-Agent': 'GardenInk-ArtStudio/1.0'})
    # System TLS verification remains enabled. No custom endpoint, proxy or base URL
    # is read from an environment variable. urllib may use standard HTTPS_PROXY.
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(API_RESPONSE_LIMIT + 1)
            request_id = response.headers.get('x-request-id', '')
        if len(payload) > API_RESPONSE_LIMIT:
            raise ApiFailure('Image response exceeded the safe response limit.')
        value = json.loads(payload)
        raw = base64.b64decode(value['data'][0]['b64_json'], validate=True)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ApiFailure('The API did not return the requested PNG.')
        metadata = {'request_id': request_id, 'usage': value.get('usage'),
                    'created': value.get('created'),
                    'revised_prompt': value['data'][0].get('revised_prompt')}
        return raw, metadata
    except urllib.error.HTTPError as exc:
        body = exc.read(65536)
        try: detail = json.loads(body).get('error', {}).get('message', '')
        except (ValueError, AttributeError): detail = ''
        detail = str(detail).replace(key, '[redacted]')[:500]
        uncertain = not (400 <= exc.code < 500)
        hint = ('Check your API project/model access, billing and account verification.'
                if exc.code in (400, 401, 403, 404) else
                'Wait for your project rate limit to recover before retrying.' if exc.code == 429 else
                'No automatic retry was made; completion/billing may be uncertain.')
        raise ApiFailure('OpenAI HTTP %s. %s %s' % (exc.code, detail, hint), uncertain) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError,
            ValueError, KeyError, IndexError, TypeError) as exc:
        raise ApiFailure('Request did not yield a usable image (%s). It may already have been processed. '
                         'No automatic retry was made.' % type(exc).__name__) from None


def normalise(raw):
    """Remove only near-white margin, retain an unquantised PNG for the app."""
    warnings = []
    with Image.open(io.BytesIO(raw)) as source:
        if source.width * source.height > 12000000:
            raise ValueError('Image exceeds the display loader\'s 12-megapixel limit.')
        if source.width < 100 or source.height < 100: raise ValueError('Returned image is too small.')
        image = Image.new('RGBA', source.size, (255, 255, 255, 255))
        image.alpha_composite(source.convert('RGBA'))
        image = image.convert('RGB')
    # Keep the untouched original separately for any future alternative preparation.
    nearwhite = image.point(lambda v: 255 if v >= 249 else v)
    diff = ImageChops.difference(nearwhite, Image.new('RGB', nearwhite.size, 'white'))
    mask = diff.convert('L').point(lambda x: 255 if x > 18 else 0)
    bounds = mask.getbbox()
    if bounds is None: raise ValueError('Returned PNG appears blank.')
    edge = []
    for x in range(0, image.width, max(1, image.width//100)):
        edge += [image.getpixel((x, 0)), image.getpixel((x, image.height-1))]
    for y in range(0, image.height, max(1, image.height//100)):
        edge += [image.getpixel((0, y)), image.getpixel((image.width-1, y))]
    if sum(min(p) >= 240 for p in edge) / len(edge) < 0.95:
        warnings.append('Non-white boundary: inspect for clipped bird, scenery or tinted background.')
    crop = nearwhite.crop(bounds)
    crop = ImageOps.contain(crop, (910, 750), RESAMPLE)
    canvas = Image.new('RGB', (960, 800), 'white')
    canvas.paste(crop, ((960-crop.width)//2, (800-crop.height)//2))
    buffer = io.BytesIO(); canvas.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue(), warnings


def panel_preview(path, size):
    """The same native colour rules used by Garden Ink 2.0's artwork loader."""
    with Image.open(path) as source:
        white = Image.new('RGBA', source.size, (255, 255, 255, 255))
        white.alpha_composite(source.convert('RGBA'))
        im = ImageOps.contain(white.convert('RGB'), size, RESAMPLE)
    bw = ImageOps.grayscale(im).convert('1', dither=DITHER)
    pixels = []
    for index, (shade, (h, s, v)) in enumerate(zip(bw.getdata(), im.convert('HSV').getdata())):
        colour = (255, 255, 255) if shade else (0, 0, 0)
        if not shade and s >= 68 and v >= 135:
            if h < 20: colour = (255, 255, 0) if h >= 10 and (index%im.width + index//im.width)%4 == 0 else (255, 0, 0)
            elif h < 48: colour = (255, 255, 0)
            elif h < 126: colour = (0, 255, 0)
            elif h < 190: colour = (0, 0, 255)
        pixels.append(colour)
    im.putdata(pixels)
    canvas = Image.new('RGB', size, 'white')
    canvas.paste(im, ((size[0]-im.width)//2, (size[1]-im.height)//2))
    return canvas


def valid_prepared(out, record):
    path = out / record.get('file', 'missing')
    return (record.get('status') in ('generated', 'approved') and path.is_file()
            and digest(path.read_bytes()) == record.get('sha256'))


def make_review(out, state):
    cards, tiles = [], []
    (out / 'previews').mkdir(parents=True, exist_ok=True)
    for item in catalogue():
        slug = item['slug']; record = state['birds'].get(slug, {})
        if not valid_prepared(out, record): continue
        image = out / record['file']
        hero = panel_preview(image, (232, 226)); thumb = panel_preview(image, (102, 100))
        hero.save(out / 'previews' / (slug + '-hero.png'))
        thumb.save(out / 'previews' / (slug + '-thumb.png'))
        escaped = html.escape(item['display_name'])
        warns = ' '.join(record.get('warnings', []))
        cards.append('''<article><h2>%s</h2><p><i>%s</i></p><p>%s</p>
<img class="original" src="%s" alt="Prepared illustration"><div class="native">
<div><img width="232" height="226" src="previews/%s-hero.png"><small>232 × 226 — main card</small></div>
<div><img width="102" height="100" src="previews/%s-thumb.png"><small>102 × 100 — thumbnail</small></div></div><p>%s</p></article>'''
                     % (escaped, html.escape(item['scientific_name']), html.escape(record['status']),
                        html.escape(record['file']), slug, slug, html.escape(warns)))
        tile = Image.new('RGB', (380, 290), 'white'); d = ImageDraw.Draw(tile)
        # PIL's own default font is used only to label the review sheet; no font binaries bundled.
        d.text((10, 5), item['display_name'], fill='black')
        d.text((10, 22), item['scientific_name'], fill='black')
        tile.paste(hero, (8, 45)); tile.paste(thumb, (264, 105))
        d.text((10, 274), record['status'], fill='black')
        tiles.append(tile)
    markup = '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Garden Ink artwork review</title>
<style>body{font:16px system-ui;background:#eee;margin:2rem;color:#111}main{display:flex;flex-wrap:wrap;gap:1.5rem}article{background:white;padding:1rem;width:390px;border:1px solid #aaa}h2{margin:0}p{margin:.5rem 0}.original{width:360px;height:300px;object-fit:contain}.native{display:flex;align-items:center;gap:10px}.native img{image-rendering:pixelated;display:block}small{display:block;font-size:11px}header{max-width:900px;margin-bottom:2rem}</style>
<header><h1>One illustrator, one garden</h1><p>Compare every bird with the original robin. Check linework, natural anatomy, colour restraint and feather detail at BOTH native card sizes. A successful PNG is not an approval of species accuracy or style.</p><p>These are source/native-RGB previews, not a measurement of physical panel pigments. No website or external image service is contacted by this page. Approve acceptable results with the CLI only after inspection.</p></header><main>%s</main></html>''' % '\n'.join(cards)
    atomic(out / 'review.html', markup.encode('utf-8'))
    if tiles:
        sheet = Image.new('RGB', (380*3, 290*((len(tiles)+2)//3)), 'white')
        for index, tile in enumerate(tiles): sheet.paste(tile, ((index%3)*380, (index//3)*290))
        sheet.save(out / 'review.png')
    print('Review: %s (%s illustrations)' % (out / 'review.html', len(cards)))


def generate(args, out):
    items = select(catalogue(), args.set, args.species)
    state = load_state(out)
    targets = []
    for item in items:
        if item['keep_reference']: continue
        previous = state['birds'].get(item['slug'], {})
        if previous.get('status') in ('in_flight', 'uncertain') and not args.retry_uncertain:
            raise RuntimeError('%s has an uncertain earlier request. Check your API activity; '
                               'use --retry-uncertain to explicitly accept possible duplicate charges.' % item['display_name'])
        if valid_prepared(out, previous) and not args.regenerate:
            if previous.get('fingerprint') != fingerprint(item, args):
                raise RuntimeError('Settings/reference/prompt changed for %s. Use a separate --output directory '
                                   'or explicitly select it with --regenerate.' % item['display_name'])
            continue
        targets.append(item)
    if args.regenerate and not args.species:
        raise ValueError('--regenerate requires explicit --species selections, never the whole catalogue by accident.')
    if args.max_calls is not None: targets = targets[:args.max_calls]
    print('Model: %s | quality: %s | %s | reference: original robin' % (args.model, args.quality, args.size))
    print('%d paid image request(s) planned; robin is retained, not regenerated.' % len(targets))
    for item in targets: print('  ' + item['scientific_name'] + ' — ' + item['display_name'])
    if args.plan: return
    if not targets:
        seed_reference(out, state); make_review(out, state); return
    if not args.yes:
        answer = input('This sends paid image-edit requests to OpenAI. Type GENERATE to proceed: ')
        if answer != 'GENERATE': print('Cancelled. No API request sent.'); return
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        if not sys.stdin.isatty(): raise ValueError('Set OPENAI_API_KEY, or run interactively for a hidden key prompt.')
        key = getpass.getpass('OpenAI API key (hidden; not saved): ').strip()
    if not key or any(c.isspace() for c in key): raise ValueError('API key must be a non-empty single token.')
    seed_reference(out, state)
    for index, item in enumerate(targets):
        slug = item['slug']; fields = request_fields(item, args)
        previous = state['birds'].get(slug)
        if previous:
            archive = out / 'history' / (slug + '-' + uuid.uuid4().hex[:10])
            write_json(archive.with_suffix('.json'), previous)
            oldpath = out / previous.get('file', 'missing')
            if oldpath.is_file(): atomic(archive.with_suffix('.png'), oldpath.read_bytes())
        record = {'status': 'in_flight', 'started_at': now(), 'fingerprint': fingerprint(item, args),
                  'model': args.model, 'quality': args.quality, 'size': args.size,
                  'prompt': fields['prompt'], 'reference_sha256': digest(REFERENCE.read_bytes())}
        state['birds'][slug] = record
        save_state(out, state)  # before the POST: a crash cannot masquerade as an unattempted bird
        print('[%d/%d] %s ...' % (index+1, len(targets), item['display_name']), flush=True)
        try:
            raw, metadata = api_edit(fields, key, args.timeout)
            atomic(out / 'raw' / (slug + '.png'), raw)
            write_json(out / 'raw' / (slug + '.json'), metadata)
            prepared, warnings = normalise(raw)
            atomic(out / 'prepared' / (slug + '.png'), prepared)
            record.update(metadata)
            record.update(status='generated', finished_at=now(), file='prepared/' + slug + '.png',
                          sha256=digest(prepared), warnings=warnings)
            save_state(out, state)
        except KeyboardInterrupt:
            record.update(status='uncertain', error='Interrupted while request may have been processing.')
            save_state(out, state)
            raise
        except Exception as exc:
            record.update(status='uncertain' if not isinstance(exc, ApiFailure) or exc.uncertain else 'failed',
                          error=str(exc).replace(key, '[redacted]')[:1000])
            save_state(out, state)
            make_review(out, state)
            raise RuntimeError('%s failed: %s\nSaved earlier successes; no automatic retry. '
                               'If raw/%s.png exists, use recover before considering another paid request.'
                               % (item['display_name'], record['error'], slug)) from None
        if index + 1 < len(targets): time.sleep(args.delay)
    make_review(out, state)
    print('Generation is finished, not automatically approved. Inspect review.html before approval/export.')


def approve(args, out):
    state = load_state(out); seed_reference(out, state)
    items = select(catalogue(), args.set, args.species)
    for item in items:
        record = state['birds'].get(item['slug'], {})
        if not valid_prepared(out, record):
            raise ValueError('No valid generated image to approve: ' + item['display_name'])
    if not args.yes:
        if input('After visually checking these %d illustrations, type APPROVE: ' % len(items)) != 'APPROVE':
            print('Approval cancelled.'); return
    for item in items:
        state['birds'][item['slug']].update(status='approved', approved_at=now())
    save_state(out, state); make_review(out, state)


def recover(args, out):
    state = load_state(out)
    for item in select(catalogue(), names=args.species):
        slug = item['slug']; record = state['birds'].get(slug, {})
        if record.get('status') not in ('uncertain', 'in_flight'):
            raise ValueError('Recover is only for interrupted requests: ' + slug)
        raw = (out / 'raw' / (slug + '.png')).read_bytes()
        # A raw result must belong to the current attempt, not an older generation.
        if (out / 'raw' / (slug + '.png')).stat().st_mtime < dt.datetime.fromisoformat(record['started_at']).timestamp():
            raise ValueError('Raw image predates the current request; refusing recovery.')
        prepared, warnings = normalise(raw)
        atomic(out / 'prepared' / (slug + '.png'), prepared)
        record.update(status='generated', finished_at=now(), file='prepared/' + slug + '.png',
                      sha256=digest(prepared), warnings=warnings, recovered=True)
        save_state(out, state)
    make_review(out, state)


def export_pack(args, out):
    state = load_state(out); seed_reference(out, state)
    selected, absent = [], []
    for item in catalogue():
        record = state['birds'].get(item['slug'], {})
        if record.get('status') == 'approved' and valid_prepared(out, record): selected.append(item)
        else: absent.append(item['scientific_name'])
    if absent and not args.allow_partial:
        raise ValueError('%d species not generated AND approved. Review/approve first, or explicitly '
                         'use --allow-partial for a proof-only pack. Missing: %s' % (len(absent), ', '.join(absent)))
    dest = Path(args.zip).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    prefix = 'garden_ink_art_pack/'
    artwork_files = {}; patch = {}; cat = []
    for item in selected:
        content = (out / state['birds'][item['slug']]['file']).read_bytes()
        for scientific in [item['scientific_name']] + item['scientific_aliases']:
            slug = scientific.casefold().replace(' ', '_')
            if not re.fullmatch('[a-z]+(?:_[a-z]+)+', slug): raise ValueError('Unsafe species filename.')
            artwork_files[slug + '.png'] = content
            patch[scientific.casefold()] = {
                'name': item['api_label'], 'display_name': item['display_name'], 'file': slug + '.png',
                'aliases': [item['display_name'].casefold(), item['api_label'].casefold()],
                'kind': 'reference-guided ink illustration, operator-approved', 'not_evidence': True}
        cat.append({key: item[key] for key in ('scientific_name', 'display_name', 'api_label')})
    info = {'created_at': now(), 'complete_catalogue': not absent,
            'species_count': len(selected), 'uncovered_species': absent,
            'reference_sha256': digest(REFERENCE.read_bytes()),
            'files': {name: digest(raw) for name, raw in artwork_files.items()}}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in artwork_files.items(): z.writestr(prefix + 'custom/' + name, content)
        for name, content in [('manifest_patch.json', patch), ('species_catalog.json', cat), ('PACK_INFO.json', info)]:
            z.writestr(prefix + name, json.dumps(content, indent=2))
        z.writestr(prefix + 'apply_art.py', (ROOT / 'apply_art.py').read_bytes())
        z.writestr(prefix + 'README.txt', 'GARDEN INK: APPROVED ROBIN-STYLE ARTWORK\n'
            'Stop the service first. Run: python3 apply_art.py ~/garden_ink\n'
            'Then: cd ~/garden_ink && ./run.sh --preview && ./service.sh start\n'
            'Hourly hardware cooldown remains unchanged. See PACK_INFO.json for completeness.\n'
            'This pack contains no API key and needs no internet connection to install.\n')
    atomic(dest, buffer.getvalue())
    print('Exported %s: %d species, %d PNG filenames (including aliases), %s.' %
          (dest, len(selected), len(artwork_files), 'FULL CATALOGUE' if not absent else 'PARTIAL PROOF PACK'))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=ROOT/'output', help='Generation state/results folder; separate folder for a new style/model.')
    subs = p.add_subparsers(dest='command', required=True)
    def selection(q):
        q.add_argument('--set', choices=['all', 'proof', 'missing'], default='all')
        q.add_argument('--species', action='append', help='Exact common/scientific name or slug. Repeat to select several.')
    q = subs.add_parser('generate'); selection(q)
    q.add_argument('--model', default=DEFAULT_MODEL)
    q.add_argument('--quality', choices=['low', 'medium', 'high'], default='high')
    q.add_argument('--size', choices=['1536x1024', '1024x1024', '1024x1536'], default='1536x1024')
    q.add_argument('--plan', action='store_true', help='No API calls and no key required.')
    q.add_argument('--yes', action='store_true', help='Approve the printed paid request plan without prompting.')
    q.add_argument('--max-calls', type=int, help='Hard per-run cap on image requests.')
    q.add_argument('--delay', type=float, default=15.0, help='Seconds between successful requests, default 15.')
    q.add_argument('--timeout', type=int, default=600)
    q.add_argument('--regenerate', action='store_true', help='Explicitly re-create selected --species only; prior result is archived.')
    q.add_argument('--retry-uncertain', action='store_true', help='Accept a possible extra charge after an interrupted/uncertain earlier POST.')
    q = subs.add_parser('approve'); selection(q); q.add_argument('--yes', action='store_true')
    subs.add_parser('review')
    subs.add_parser('list')
    q = subs.add_parser('recover'); q.add_argument('--species', action='append', required=True)
    q = subs.add_parser('export'); q.add_argument('--zip', default=str(ROOT/'garden_ink_robin_art.zip'))
    q.add_argument('--allow-partial', action='store_true')
    return p


def main():
    args = parser().parse_args(); out = args.output.expanduser().resolve()
    if args.command == 'generate':
        if args.max_calls is not None and args.max_calls < 1: raise ValueError('--max-calls must be positive.')
        if not 0 <= args.delay <= 3600: raise ValueError('--delay must be in 0..3600.')
        if not 30 <= args.timeout <= 1800: raise ValueError('--timeout must be in 30..1800.')
        if not re.fullmatch('[a-zA-Z0-9._-]{1,100}', args.model): raise ValueError('Invalid model name.')
        if args.plan: generate(args, out); return
    if args.command == 'list':
        state = load_state(out)
        for item in catalogue():
            record = state['birds'].get(item['slug'], {})
            print('%-26s %-34s %s' % (item['display_name'], item['scientific_name'], 'original reference' if item['keep_reference'] else record.get('status','not generated')))
        return
    with locked(out):
        if args.command == 'generate': generate(args, out)
        elif args.command == 'approve': approve(args, out)
        elif args.command == 'export': export_pack(args, out)
        elif args.command == 'recover': recover(args, out)
        elif args.command == 'review':
            state = load_state(out); seed_reference(out, state); make_review(out, state)

if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt:
        print('\nInterrupted. Completed images retained; in-flight requests are marked uncertain.', file=sys.stderr)
        sys.exit(130)
    except (RuntimeError, ValueError, OSError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr); sys.exit(1)
