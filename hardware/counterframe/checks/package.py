from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json,base64,zipfile,html
ROOT=Path(__file__).resolve().parents[1]; R=ROOT/'renders'
BG=(243,244,241); INK=(32,49,44); MUTE=(81,95,88)
def font(size,bold=False):
 return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',size)
# Four manufacturing parts, all actual STL renders.
im=Image.new('RGB',(1800,1720),BG);d=ImageDraw.Draw(im)
d.text((65,38),'COUNTERFRAME / PRINTED COMPONENTS',font=font(40,True),fill=INK)
d.text((65,95),'Four structural PLA prints. Colours distinguish parts; a single colour is fine.',font=font(24),fill=MUTE)
tiles=[('front_part','01  Front bezel','Glass seat and separate latch windows'),
       ('carrier_part','02  Internal carrier','Tapered locating posts and ribbon guides'),
       ('rear_part','03  Rear cover','Twelve annular PCB retainers; snap-fit closure'),
       ('stand_part','04  Solid PLA stand','Wide plinth, angled cradle and printed detents')]
for i,(name,title,caption) in enumerate(tiles):
 x=55+(i%2)*875;y=155+(i//2)*755
 d.text((x+15,y),title,font=font(31,True),fill=INK)
 pic=Image.open(R/(name+'.png')).convert('RGB').resize((810,675),Image.Resampling.LANCZOS)
 im.paste(pic,(x+5,y+45))
 d.text((x+15,y+716),caption,font=font(21),fill=MUTE)
im.save(R/'components.png')
# Annotated rear-open render. Numbers refer to actual projected geometry locations.
im=Image.new('RGB',(1900,1570),BG);d=ImageDraw.Draw(im)
d.text((65,32),'COUNTERFRAME / INTERNAL LAYOUT',font=font(40,True),fill=INK)
d.text((65,91),'Rear cover removed. Hardware envelopes are approximate; this is not a wiring pinout.',font=font(23),fill=MUTE)
pic=Image.open(R/'internal.png').convert('RGB');scale=.75;px=275;py=135
im.paste(pic.resize((1350,1125),Image.Resampling.LANCZOS),(px,py))
anchors=json.loads((R/'internal_anchors.json').read_text())
legend=[('Pi','Raspberry Pi Zero'),('HAT','Dedicated (E) driver HAT'),('Adapter','Separate FPC adapter'),
        ('Bonded flex','Bonded panel tail / gentle return'),('FFC','Matched 50 mm FFC / single arch'),('USB','USB jacket saddle / underside exit')]
for i,(k,t) in enumerate(legend,1):
 x=px+scale*anchors[k][0];y=py+scale*anchors[k][1]
 d.ellipse((x-23,y-23,x+23,y+23),fill=INK,outline=(244,246,240),width=3)
 d.text((x,y),str(i),font=font(23,True),fill='white',anchor='mm')
 col=(i-1)%2;row=(i-1)//2;lx=90+col*920;ly=1290+row*72
 d.ellipse((lx,ly,lx+40,ly+40),fill=INK)
 d.text((lx+20,ly+20),str(i),font=font(22,True),fill='white',anchor='mm')
 d.text((lx+57,ly+5),t,font=font(25),fill=INK)
d.text((90,1520),'One external power lead. No mechanical screws, glue, inserts, metal ballast or elastomer feet.',font=font(22),fill=MUTE)
im.save(R/'routing.png')
# An offline, self-contained illustrated guide, with no font files or external scripts.
import mistune
body=mistune.create_markdown(plugins=['table','url'])((ROOT/'README.md').read_text())
def embed(name,alt):
 b=base64.b64encode((R/(name+'.png')).read_bytes()).decode()
 return f'<img src="data:image/png;base64,{b}" alt="{html.escape(alt)}">'
visuals=''.join('<figure>'+embed(n,a)+'<figcaption>'+a+'</figcaption></figure>' for n,a in [
 ('assembled','Assembled CAD render. Illustrative content on the display.'),
 ('components','The four structural prints. Individual STL geometry in print orientation.'),
 ('routing','Open-rear layout, including the short replacement FFC and single USB power lead.'),
 ('exploded','Exploded geometry view. Cables omitted for clarity.'),
 ('rear_view','Tapered rear cover and cable exit behind the stand.'),
 ('side_view','The 10-degree lean and thin visible perimeter, with space behind for connectors.')])
css='''body{margin:0;background:#f3f4f1;color:#24362e;font:17px/1.6 system-ui,sans-serif}main{max-width:1050px;margin:0 auto;padding:45px 32px 90px}h1{font-size:44px;line-height:1.1}h2{margin-top:2.3em;border-top:1px solid #cad2ca;padding-top:18px}h3{margin-top:1.8em}a{color:#315d55}table{width:100%;border-collapse:collapse;font-size:15px;margin:22px 0}th,td{padding:11px 13px;border-bottom:1px solid #cdd5cc;text-align:left;vertical-align:top}th{background:#e2e8df}blockquote{margin:25px 0;padding:10px 22px;background:#f3e9d7;border-left:4px solid #ad8055}pre{background:#e2e8df;padding:18px;overflow:auto}code{font-size:.87em}img{display:block;width:100%;height:auto}figure{margin:30px 0 55px}figcaption{font-size:14px;color:#5e6f63;padding:10px 4px}header small{letter-spacing:3px;font-size:13px}.tag{display:inline-block;background:#dce6db;padding:5px 12px;border-radius:5px;margin:6px 9px 6px 0;font-size:14px}section#guide{margin-top:70px}li{margin-bottom:9px}@media print{body{background:white}main{padding:0;font-size:11pt}figure,table{break-inside:avoid}h2{break-after:avoid}img{max-height:230mm;object-fit:contain}}'''
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Counterframe — illustrated build guide</title><style>'+css+'</style></head><body><main><header><small>COUNTERFRAME / 7.3 E6 / V1.0</small><h1>A quiet place for a changing screen.</h1><p>Portrait countertop enclosure for the Pi Zero and Waveshare Spectra 6 (E).</p><span class="tag">4 structural PLA parts</span><span class="tag">0 screws</span><span class="tag">142 × 108 × 195 mm assembled</span><blockquote><strong>Engineering prototype, not physically print- or fit-tested.</strong> Confirm the exact (E) hardware, a matched 50 mm FFC and the slim USB plug before the full print.</blockquote></header>'+visuals+'<section id="guide">'+body+'</section></main></body></html>'
(ROOT/'BUILD_GUIDE.html').write_text(page)
# Exclude development fixes, stale previews and interference-result STLs.
full=ROOT.parent/'Counterframe_complete_design.zip'
checks={'run_collision.sh','export_render_meshes.py','validate.py','package.py'}
with zipfile.ZipFile(full,'w',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(ROOT)
  if '__pycache__' in rel.parts:continue
  if rel.parts[0]=='checks':
   if p.name not in checks and p.suffix!='.scad':continue
  if p.name in ['assembly_openscad.png','internal_anchors.json']:continue
  z.write(p,'Counterframe/'+str(rel))
with zipfile.ZipFile(ROOT.parent/'Counterframe_print_STLs.zip','w',zipfile.ZIP_DEFLATED,compresslevel=8) as z:
 for p in sorted((ROOT/'stl').glob('*.stl')):z.write(p,'stl/'+p.name)
 z.write(ROOT/'README.md','README.md');z.write(ROOT/'validation.json','validation.json')
print('Packaged',full,full.stat().st_size)
print('STL pack',(ROOT.parent/'Counterframe_print_STLs.zip').stat().st_size)
