"""Fixed-endpoint Images API adapter. No POST retries; no remote error bodies in logs."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import socket
import threading
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from PIL import Image, ImageChops, ImageOps
from .config import ROOT

ENDPOINT = 'https://api.openai.com/v1/images/edits'
REFERENCE = ROOT/'autoart_reference'/'robin.png'
MAX_RESPONSE = 24 * 1024 * 1024
PREPARE_LOCK = threading.Lock()


class ApiFailure(RuntimeError):
    def __init__(self, message, uncertain=True, status=0, request_id=''):
        super().__init__(message)
        self.uncertain, self.status = uncertain, status
        self.request_id = request_id[:160]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fields_for(scientific, note, cfg):
    items=json.loads((ROOT/'autoart_reference'/'species.json').read_text())
    item=next((i for i in items if scientific.casefold() in
               [i['scientific_name'].casefold()]+[n.casefold() for n in i.get('scientific_aliases',[])]), {})
    style=(ROOT/'autoart_reference'/'STYLE_BRIEF.txt').read_text()
    pose=item.get('pose') or ('A natural species-appropriate standing or perched pose. '
                             'Keep the whole bird visible; do not perch a waterbird on a twig.')
    extra=(item.get('note') or '')+'\n'+note
    extra+='\nAnatomy: one bird, exactly two legs in total, at most two visible feet. No extra limbs or duplicate toes/feet. Preserve species anatomy, not robin proportions.'
    prompt=style.format(api_label=item.get('api_label') or scientific,
                        scientific_name=scientific, pose=pose, note=extra)
    return {'model':cfg['model'], 'prompt':prompt, 'n':'1', 'size':'1536x1024',
            'quality':'high', 'background':'opaque', 'output_format':'png'}


def request_fingerprint(scientific, note, cfg):
    data={'fields':fields_for(scientific,note,cfg),
          'reference_sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest()}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def multipart(fields, image):
    boundary='gardenink-'+uuid.uuid4().hex
    body=bytearray()
    for key,value in fields.items():
        body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+str(value)+'\r\n').encode())
    body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="image[]"; filename="robin.png"\r\nContent-Type: image/png\r\n\r\n').encode())
    body.extend(image)
    body.extend(('\r\n--'+boundary+'--\r\n').encode())
    return bytes(body),'multipart/form-data; boundary='+boundary


def api_edit(scientific, note, cfg, key):
    data,content_type=multipart(fields_for(scientific,note,cfg),REFERENCE.read_bytes())
    request=urllib.request.Request(ENDPOINT,data=data,method='POST',headers={
        'Authorization':'Bearer '+key, 'Content-Type':content_type,
        'Accept':'application/json', 'User-Agent':'GardenInk-AutoArt/2.1'})
    request_id=''
    try:
        # Default CA verification stays enabled. No redirects or alternative endpoint.
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=cfg['timeout_seconds']) as response:
            request_id=response.headers.get('x-request-id','')[:160]
            payload=response.read(MAX_RESPONSE+1)
        if len(payload)>MAX_RESPONSE: raise ApiFailure('Response exceeded size limit.',request_id=request_id)
        value=json.loads(payload)
        raw=base64.b64decode(value['data'][0]['b64_json'],validate=True)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'): raise ApiFailure('Response was not a PNG.',request_id=request_id)
        return raw, {'request_id':request_id, 'usage':value.get('usage'), 'created':value.get('created')}
    except urllib.error.HTTPError as exc:
        # Never print the API response: some auth errors echo part of the key.
        rid=exc.headers.get('x-request-id','') if exc.headers else ''
        exc.close()
        raise ApiFailure('OpenAI HTTP %d; no automatic retry.'%exc.code,
                         uncertain=not (400<=exc.code<500),status=exc.code,request_id=rid) from None
    except (urllib.error.URLError,socket.timeout,TimeoutError,ConnectionError,
            ValueError,KeyError,IndexError,TypeError,OSError) as exc:
        raise ApiFailure('No usable image received (%s); outcome uncertain.'%type(exc).__name__,
                         request_id=request_id) from None


def normalise(raw):
    """White canvas, bounded memory. PNG checks cannot validate species/anatomy."""
    with PREPARE_LOCK:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format!='PNG' or not 100<=source.width or not 100<=source.height:
                raise ValueError('Expected a usable PNG')
            if source.width*source.height>4000000: raise ValueError('Image exceeds four megapixels')
            image=Image.new('RGBA',source.size,(255,255,255,255))
            image.alpha_composite(source.convert('RGBA'))
            image=image.convert('RGB')
        nearwhite=image.point(lambda v:255 if v>=249 else v)
        diff=ImageChops.difference(nearwhite,Image.new('RGB',nearwhite.size,'white'))
        box=diff.convert('L').point(lambda v:255 if v>18 else 0).getbbox()
        if not box: raise ValueError('Blank image')
        if box[0]==0 or box[1]==0 or box[2]==image.width or box[3]==image.height:
            warning='Artwork touches edge; inspect composition.'
        else: warning=''
        crop=ImageOps.contain(nearwhite.crop(box),(910,750),getattr(Image,'Resampling',Image).LANCZOS)
        canvas=Image.new('RGB',(960,800),'white')
        canvas.paste(crop,((960-crop.width)//2,(800-crop.height)//2))
        output=io.BytesIO();canvas.save(output,format='PNG',optimize=True)
        return output.getvalue(),warning
