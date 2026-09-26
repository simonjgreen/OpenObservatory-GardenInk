#!/usr/bin/env python3
"""Build the additional decorative bird assets. Build-time only: needs CairoSVG.

These are stylised, programmatically drawn illustrations, not scientific plates
or observed evidence. The runtime uses the pre-rendered PNGs, not this script.
"""
from pathlib import Path
import random
import json
import math

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets'/'birds'
SRC=ROOT/'artwork_sources'
INK='#202521'; PALE='#eeeade'; GREY='#a3ada8'; BROWN='#a58863'; DARK='#514c42'

CATALOG=[
('Erithacus rubecula','Robin','European Robin'),
('Columba palumbus','Woodpigeon','Common Woodpigeon'),
('Corvus monedula','Jackdaw','Eurasian Jackdaw'),
('Corvus frugilegus','Rook','Rook'),
('Cyanistes caeruleus','Blue Tit','Eurasian Blue Tit'),
('Aegithalos caudatus','Long-tailed Tit','Long-tailed Tit'),
('Streptopelia decaocto','Collared Dove','Collared Dove'),
('Prunella modularis','Dunnock','Dunnock'),
('Turdus merula','Blackbird','Eurasian Blackbird'),
('Carduelis carduelis','Goldfinch','European Goldfinch'),
('Strix aluco','Tawny Owl','Tawny Owl'),
('Pica pica','Magpie','Common Magpie'),
('Delichon urbicum','House Martin','Western House Martin'),
('Chloris chloris','Greenfinch','European Greenfinch'),
('Troglodytes troglodytes','Wren','Eurasian Wren'),
('Muscicapa striata','Spotted Flycatcher','Spotted Flycatcher'),
('Regulus regulus','Goldcrest','Goldcrest'),
('Fringilla coelebs','Chaffinch','Common Chaffinch'),
('Dendrocopos major','Great Spotted Woodpecker','Great Spotted Woodpecker'),
('Parus major','Great Tit','Great Tit'),
('Sitta europaea','Nuthatch','Eurasian Nuthatch'),
('Hirundo rustica','Swallow','Barn Swallow'),
('Branta canadensis','Canada Goose','Canada Goose'),
('Columba oenas','Stock Dove','Stock Dove'),
('Corvus corone','Carrion Crow','Carrion Crow'),
('Phasianus colchicus','Pheasant','Common Pheasant'),
('Sylvia atricapilla','Blackcap','Eurasian Blackcap'),
('Picus viridis','Green Woodpecker','Eurasian Green Woodpecker'),
('Turdus philomelos','Song Thrush','Song Thrush'),
('Ardea cinerea','Grey Heron','Grey Heron'),
('Alcedo atthis','Kingfisher','Common Kingfisher'),
('Columba livia','Rock Dove','Rock Dove'),
('Buteo buteo','Buzzard','Common Buzzard'),
('Phylloscopus collybita','Chiffchaff','Common Chiffchaff'),
('Corvus corax','Raven','Common Raven'),
('Periparus ater','Coal Tit','Coal Tit'),
('Sturnus vulgaris','Starling','Common Starling'),
('Motacilla cinerea','Grey Wagtail','Grey Wagtail'),
('Garrulus glandarius','Jay','Eurasian Jay'),
('Anas platyrhynchos','Mallard','Mallard'),
('Turdus iliacus','Redwing','Redwing'),
('Milvus milvus','Red Kite','Red Kite'),
('Motacilla alba','Pied Wagtail','Pied Wagtail/White Wagtail'),
('Fulica atra','Coot','Eurasian Coot'),
('Porzana porzana','Spotted Crake','Spotted Crake'),
('Gallinula chloropus','Moorhen','Common Moorhen'),
('Passer domesticus','House Sparrow','House Sparrow'),
]

class Drawing:
    def __init__(self):
        self.s=['<svg xmlns="http://www.w3.org/2000/svg" width="640" height="500" viewBox="0 0 640 500">',
                '<rect width="640" height="500" fill="white"/>']
    def path(self,d,fill='none',stroke=INK,width=1.5,extra=''):
        self.s.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round" {extra}/>')
    def ellipse(self,cx,cy,rx,ry,fill=PALE,stroke=INK,width=1.3,extra=''):
        self.s.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" {extra}/>')
    def eye(self,x,y,r=6,iris=PALE):
        self.ellipse(x,y,r+1.6,r+1.6,iris,width=1)
        self.ellipse(x,y,r*.72,r*.72,INK,width=0)
        self.ellipse(x-1.5,y-1.4,1.5,1.5,'white',width=0)
    def hatch(self,clip,seed=1,colour='#66645b',count=400):
        rng=random.Random(seed)
        self.s.append(f'<g clip-path="url(#{clip})">')
        for i in range(count):
            x,y=rng.uniform(100,510),rng.uniform(60,397)
            l=rng.uniform(3,10)
            self.path(f'M{x:.1f} {y:.1f} q{l/2:.1f} {rng.uniform(0,3):.1f} {l:.1f} -{l/3:.1f}',stroke=colour,width=.75)
        self.s.append('</g>')
    def clip(self,ident,d):
        self.s.append(f'<defs><clipPath id="{ident}"><path d="{d}"/></clipPath></defs>')
    def branch(self):
        self.path('M112 413 Q240 403 356 408 Q420 403 496 392 M109 421 Q269 412 352 416 M402 406 l29 14',width=2)
        for x in range(128,454,23):self.path(f'M{x} 412 l12 -2',width=.7)
    def finish(self):return '\n'.join(self.s+['</svg>'])

BODY='M190 354 C161 317 169 254 221 207 C253 183 282 176 310 152 C309 118 337 89 377 86 C422 82 453 112 455 140 C455 157 446 173 429 186 C456 226 454 278 422 316 C382 365 277 377 190 354 Z'
WING='M331 190 C281 173 223 211 200 259 L149 352 C215 343 286 320 331 277 C354 253 361 215 331 190 Z'


def passerine(sci):
    d=Drawing(); rng=random.Random(sci)
    opts={
    'Chloris chloris':('#a2a15d','#737947','#bbc16c','cone'),
    'Muscicapa striata':('#a89e8c','#796f60','#ebe5d8','fine'),
    'Regulus regulus':('#8a9470','#59665b','#e3ddc2','fine'),
    'Dendrocopos major':('#e8e8da','#222d29','#eeeede','chisel'),
    'Sylvia atricapilla':('#b0aaa0','#7c8074','#d7d6c8','fine'),
    'Picus viridis':('#8e9b50','#60733c','#c4c592','chisel'),
    'Turdus philomelos':('#a08c70','#736149','#eee2c5','fine'),
    'Alcedo atthis':('#75a3a7','#3b858c','#c58e59','dagger'),
    'Phylloscopus collybita':('#a1a284','#758067','#e7e1bc','fine'),
    'Corvus corax':('#2f3433','#343b39','#333936','crow'),
    'Periparus ater':('#ddd8c7','#71766b','#ded9c6','fine'),
    'Motacilla cinerea':('#929e9b','#636d6c','#ddcc67','fine'),
    'Turdus iliacus':('#9b8a71','#695d4b','#ebe2ca','fine'),
    'Motacilla alba':('#bdc3bd','#4e5b57','#eeeeE4','fine'),
    }
    body,wing,breast,bill=opts[sci]
    long=sci in ('Motacilla cinerea','Motacilla alba')
    tail='M202 300 L42 431 L260 332 Z' if long else 'M210 300 L99 399 L263 334 Z'
    d.path(tail,fill=wing,width=2)
    for i in range(8):d.path(f'M{204+i*6} {315+i} L{(44 if long else 105)+i*7} {425-i*3}',stroke='#858b7f',width=1)
    d.path(BODY,fill=body,width=2);d.clip('body',BODY)
    d.ellipse(379,279,70,85,breast,stroke='none',extra='clip-path="url(#body)"')
    if sci=='Corvus corax':
        d.path('M437 132 Q476 120 507 143 L510 156 Q493 151 466 154 L441 160 Z',fill=INK,width=2)
        for j in range(7):d.path(f'M{420-j*5} 172 l{j-2} {29+j*2} l-8 -12',fill=INK)
    else:
        tips={'cone':(487,148),'fine':(493,150),'chisel':(521,150),'dagger':(556,149)}
        tx,ty=tips[bill]
        d.path(f'M441 138 L{tx} {ty} L441 157 Z',fill='#797863' if bill=='cone' else INK)
        d.path(f'M448 149 L{tx-3} {ty}',stroke='#ddd6bc',width=.7)
    if sci in ('Sylvia atricapilla','Periparus ater','Motacilla alba'):
        d.path('M310 145 C312 83 409 60 447 116 L438 139 Q366 129 317 160 Z',fill=INK,extra='clip-path="url(#body)"')
    if sci=='Periparus ater':
        d.ellipse(401,164,31,23,PALE,stroke='none')
        d.path('M361 179 L433 176 L407 228 L372 211 Z',fill=INK)
        d.path('M310 124 L327 113 L337 159 L315 166 Z',fill=PALE)
    if sci=='Motacilla alba':
        d.ellipse(402,160,27,25,PALE,stroke='none')
        d.path('M411 185 L442 178 L439 246 L382 234 L358 201 Z',fill=INK)
    if sci in ('Regulus regulus','Dendrocopos major','Picus viridis'):
        cap='#e1c74e' if sci=='Regulus regulus' else '#b25749'
        d.path('M324 119 Q363 72 419 104 L433 121 Q374 94 340 140 Z',fill=cap,width=1)
        if sci=='Regulus regulus':
            d.path('M328 131 Q370 90 427 118',width=5)
            d.path('M331 122 Q368 84 420 104',width=4)
        else:
            d.ellipse(397,168,31,22,PALE,stroke='none')
            d.path('M391 176 L416 177 L425 227 L408 227 Z',fill=INK)
    if sci in ('Turdus philomelos','Turdus iliacus','Muscicapa striata'):
        if sci=='Turdus iliacus':
            d.ellipse(300,300,50,50,'#b77752',stroke='none',extra='clip-path="url(#body)"')
            d.path('M363 130 Q406 110 440 129',stroke=PALE,width=9)
        for _ in range(40 if sci!='Muscicapa striata' else 25):
            x,y=rng.uniform(337,433),rng.uniform(191,331)
            d.path(f'M{x:.0f} {y:.0f} l-2 9 l5 -5 Z',fill=DARK,width=.4,extra='clip-path="url(#body)"')
    if sci=='Alcedo atthis':
        d.ellipse(408,169,25,12,PALE,stroke='none')
        d.path('M341 155 L385 147 L390 171 L345 178 Z',fill='#c78e55')
    if sci=='Motacilla cinerea':
        d.path('M361 133 Q402 119 441 136',stroke=PALE,width=6)
    d.hatch('body',seed=len(sci)*3,colour='#7a7e70' if sci!='Corvus corax' else '#aab0a4',count=380)
    d.path(WING,fill=wing,width=2);d.clip('wing',WING)
    for i in range(19):
        x=193+i*8
        d.path(f'M{x} 232 Q{x-10} 273 {125+i*10} 356',stroke='#b5b8a6',width=.9,extra='clip-path="url(#wing)"')
    for row in range(5):
        for col in range(7):
            x=239+col*13-row*8; y=214+row*13
            d.path(f'M{x} {y} q-9 9 -1 17 q11 2 14 -9',stroke='#b4b4a1',width=.7,extra='clip-path="url(#wing)"')
    if sci in ('Chloris chloris','Regulus regulus','Dendrocopos major','Picus viridis','Periparus ater','Motacilla alba'):
        if sci=='Dendrocopos major':
            d.ellipse(290,223,36,22,PALE,extra='clip-path="url(#wing)"')
            for y in range(255,334,18):
                for x in range(200,294,25):d.ellipse(x,y,7,5,PALE,width=.4,extra='clip-path="url(#wing)"')
            d.path('M289 355 Q351 375 393 333 L366 339 L313 342 Z',fill='#ba5748')
        elif sci=='Chloris chloris':
            d.path('M294 238 L191 326',stroke='#dacc54',width=11,extra='clip-path="url(#wing)"')
        else:
            for yy in (238,260):d.path(f'M223 {yy} Q276 {yy-18} 328 {yy-3}',stroke=PALE,width=6,extra='clip-path="url(#wing)"')
    d.eye(416,136,5.8,iris='#bbc1b0' if sci=='Corvus corax' else PALE)
    leg='#a37151' if sci=='Alcedo atthis' else DARK
    d.path('M272 353 L279 390 L297 404 M350 344 L354 393 L373 404 M276 391 L255 406 M354 393 L333 409',stroke=leg,width=3)
    d.path('M297 404 l12 0 M255 406 l-6 -3 M333 409 l-7 -4 M373 404 l9 -3',width=1.4)
    d.branch()
    return d.finish()


def pigeon(sci):
    d=Drawing(); collared=sci=='Streptopelia decaocto'
    base='#b8b5a7' if collared else '#a6b2b0';wing='#b5b09e' if collared else '#778b8b'
    d.path('M219 317 L113 405 L170 411 L288 332 Z',fill=wing,width=2)
    body='M190 327 C151 268 185 225 253 209 Q342 183 349 147 C347 116 359 86 395 89 C430 85 452 114 445 142 L436 170 C481 266 439 336 376 351 Q280 381 190 327 Z'
    d.path(body,fill=base,width=2);d.clip('b',body)
    d.path('M290 211 Q261 212 207 256 L143 370 Q253 375 360 283 Q360 229 290 211 Z',fill=wing,width=2)
    for i in range(18):d.path(f'M{239+i*6} {238+i//3} Q{260+i*4} 302 {147+i*8} 365',stroke='#d4d5c5',width=1)
    if collared:d.path('M351 173 Q365 188 393 183',stroke=INK,width=7)
    else:
        d.path('M355 163 Q376 188 411 165 L427 207 Q397 224 366 216 Z',fill='#779389',stroke='none')
        for y in (264,292):d.path(f'M222 {y} Q291 {y-18} 323 {y+5}',stroke=INK,width=9 if sci=='Columba livia' else 5)
    d.hatch('b',count=430,colour='#777f72')
    d.path('M438 125 L481 134 L441 146 Z',fill='#444942')
    if sci=='Columba livia':d.ellipse(446,128,8,4,PALE)
    d.eye(416,121,5,iris='#bd9160')
    d.path('M291 349 L280 399 M354 351 L362 399 M280 399 l-26 10 M280 399 l19 9 M362 399 l-27 12 M362 399 l23 8',stroke='#98775f',width=3)
    d.branch();return d.finish()


def owl():
    d=Drawing()
    d.path('M231 341 L233 420 L338 418 L353 334 Z',fill=DARK,width=2)
    body='M203 360 Q167 261 200 180 Q191 99 231 68 Q287 37 338 76 Q377 115 365 175 Q416 267 369 370 Q289 418 203 360 Z'
    d.path(body,fill=BROWN,width=2);d.clip('b',body)
    d.ellipse(283,138,86,73,'#ac906a',width=2)
    for x in (246,323):
        d.ellipse(x,135,36,44,'#d7c7a6',width=2)
        for a in range(22):
            angle=a/22*math.tau
            xx=x+math.cos(angle)*31; yy=135+math.sin(angle)*38
            d.path(f'M{xx} {yy} l{math.cos(angle)*-6} {math.sin(angle)*-6}',stroke='#8e7657',width=1)
        d.eye(x,130,11,iris='#63553f')
    d.path('M275 145 L298 145 L286 180 Z',fill='#7d795a')
    d.path('M219 198 Q172 234 204 357 Q257 323 246 230 Z',fill='#77654e')
    d.path('M349 196 Q395 241 368 359 Q317 321 330 229 Z',fill='#77654e')
    d.hatch('b',count=1300,colour='#5d4e3d')
    for y in range(214,370,25):
        for x in range(249,331,22):d.path(f'M{x} {y} l0 15 m-6 -10 l12 4',stroke=DARK,width=2)
    for x in (244,316):
        d.path(f'M{x} 381 l-3 33 m3 -33 l7 32 m-5 -32 l17 28',stroke='#9a9176',width=5)
    d.branch();return d.finish()


def swallow(sci):
    d=Drawing(); martin=sci=='Delichon urbicum';base='#354851'
    d.path('M278 302 L142 437 L239 386 L278 349 L290 429 L322 312 Z',fill=base,width=2)
    body='M258 324 Q214 271 263 224 L349 163 Q379 144 400 162 Q415 178 398 201 Q360 255 340 300 Q300 344 258 324 Z'
    d.path(body,fill=base,width=2);d.clip('b',body)
    d.path('M269 312 Q260 284 320 218 L388 193 Q381 241 335 301 Q300 338 269 312 Z',fill=PALE,width=1)
    if not martin:d.path('M362 198 L391 176 L401 201 L377 225 Z',fill='#a6614b')
    if martin:d.path('M250 294 L263 318 L294 326 L294 304 Z',fill='white')
    # Both swept wings carry separately drawn primaries.
    d.path('M283 252 Q219 186 159 112 L61 56 Q126 186 217 283 Z',fill=base,width=2)
    d.path('M337 243 Q406 181 505 125 L568 116 Q475 222 350 279 Z',fill=base,width=2)
    for i in range(14):
        d.path(f'M{282-i*4} {255-i*2} Q{155+i*3} {176-i*2} {62+i*7} {61+i*7}',stroke='#91a2a1',width=1)
        d.path(f'M{342+i} {249+i*2} Q{451+i*3} {194+i} {564-i*7} {121+i*5}',stroke='#91a2a1',width=1)
    d.path('M396 175 L436 174 L403 186 Z',fill=INK)
    d.eye(389,170,4)
    d.hatch('b',count=170,colour='#9bafa9')
    return d.finish()


def waterbird(sci):
    d=Drawing();goose=sci=='Branta canadensis';duck=sci=='Anas platyrhynchos'
    if goose:
        body='M136 333 Q83 304 120 260 Q174 212 303 243 Q349 244 355 189 L348 111 Q346 56 387 56 Q430 57 429 95 Q421 118 392 120 L401 205 Q448 280 393 328 Q271 382 136 333 Z'
        d.path(body,fill='#a1957d',width=2);d.clip('b',body)
        d.path('M355 205 L350 97 Q347 61 387 60 Q429 54 427 94 Q415 119 392 120 L397 210 Z',fill=INK)
        d.path('M372 95 Q395 102 416 91 L415 109 L389 123 L371 113 Z',fill=PALE)
        d.path('M418 84 L468 91 L421 101 Z',fill=INK)
        d.eye(406,83,4)
    elif duck:
        body='M105 321 Q75 274 145 252 Q226 226 332 247 Q369 246 372 189 Q366 137 406 126 Q447 121 458 148 Q466 186 425 197 L432 241 Q457 311 387 343 Q220 379 105 321 Z'
        d.path(body,fill='#bab7a6',width=2);d.clip('b',body)
        d.path('M371 197 L373 164 Q379 121 422 128 Q461 130 461 155 Q462 184 426 197 L430 236 Q398 246 371 228 Z',fill='#486c5c')
        d.path('M370 221 Q396 239 429 225',stroke=PALE,width=7)
        d.path('M370 233 Q398 246 432 237 L430 286 L358 279 Z',fill='#826957')
        d.path('M454 153 L518 159 Q526 174 510 178 L453 176 Z',fill='#d2b45a',width=1)
        d.eye(441,149,5)
    else:
        coot=sci=='Fulica atra';moor=sci=='Gallinula chloropus'
        colour='#48514e' if coot or moor else '#a09770'
        body='M143 334 Q111 288 162 255 Q216 217 317 221 Q358 209 368 178 Q373 145 409 148 Q444 150 449 179 Q451 200 427 211 Q451 242 436 286 Q402 347 339 358 Q215 385 143 334 Z'
        d.path(body,fill=colour,width=2);d.clip('b',body)
        bill='#e8e3d1' if coot else '#b55e45' if moor else '#b2a262'
        d.path('M442 170 L494 183 L444 191 Z',fill=bill)
        if coot or moor:d.ellipse(434,170,9,20,bill,width=1)
        if moor:
            d.path('M480 179 L496 183 L480 187 Z',fill='#cfc369')
            d.path('M189 292 Q274 307 320 291',stroke=PALE,width=5)
        if sci=='Porzana porzana':
            rng=random.Random(34)
            for _ in range(180):
                x,y=rng.uniform(160,420),rng.uniform(198,354)
                d.ellipse(x,y,1.7,3,PALE,stroke='none',extra='clip-path="url(#b)"')
        d.eye(422,171,4.5,iris='#a36e45')
    d.path('M174 261 Q235 240 298 258 Q370 279 337 320 Q221 360 145 329 Z',fill='#897e65' if goose else '#93968a' if duck else '#49524b',width=1.8)
    for i in range(17):d.path(f'M{162+i*9} 277 q30 28 71 34',stroke='#c9c2a9',width=.9)
    d.hatch('b',count=550,colour='#696d60')
    leg='#bb8c54' if duck else '#9b9b5c' if sci in ('Porzana porzana','Gallinula chloropus') else '#747663'
    for x in (250,327):
        d.path(f'M{x} 356 l-2 42 l-20 15 m20 -15 l24 14 m-22 -15 l-4 21',stroke=leg,width=4)
        if duck or goose:d.path(f'M{x-2} 398 l-20 15 l17 -1 l24 0 Z',fill=leg,width=1)
    d.path('M104 422 Q181 425 247 421 M289 424 L430 424 M173 435 L333 434',width=1)
    return d.finish()


def heron():
    d=Drawing()
    body='M196 300 Q150 258 187 222 Q223 196 293 218 L358 215 Q382 204 350 177 Q325 151 351 120 Q376 90 402 87 L450 85 Q470 87 470 102 Q466 116 439 118 L400 122 Q380 130 384 144 Q438 185 405 224 Q375 274 308 294 Q249 324 196 300 Z'
    d.path(body,fill='#b9c1b8',width=2);d.clip('b',body)
    d.path('M449 91 L562 107 L447 109 Z',fill='#bba672',width=1.3)
    d.path('M375 92 Q418 66 453 86 L460 92 L408 93 L371 114 L341 138',fill=INK,width=2)
    d.path('M391 133 Q342 154 386 195 L375 237',stroke=PALE,width=15)
    d.eye(442,95,4.5,iris='#e0c87d')
    d.path('M276 222 Q213 198 194 240 L161 304 Q223 320 306 266 Z',fill='#879590',width=2)
    for i in range(18):d.path(f'M{200+i*5} 231 Q{200+i*7} 273 {167+i*8} 305',stroke=PALE,width=.9)
    d.hatch('b',count=450,colour='#74796b')
    d.path('M245 308 L240 378 L252 451 L216 461 M296 300 L315 374 L333 451 L303 461 M253 451 l32 10 M333 451 l33 4',stroke='#857e5e',width=4)
    d.path('M130 466 Q262 459 399 468 M218 480 l99 -2',width=1)
    return d.finish()


def pheasant():
    d=Drawing()
    d.path('M262 283 L26 414 Q116 420 306 324 Z',fill='#b1976d',width=2)
    for i in range(14):d.path(f'M{79+i*12} {388-i*4} l-1 20',stroke=DARK,width=2)
    body='M257 327 Q217 269 271 237 Q315 221 362 237 Q383 233 380 190 Q377 163 405 153 Q433 140 452 165 Q463 187 444 202 L457 237 Q475 282 423 318 Q348 364 257 327 Z'
    d.path(body,fill='#b19368',width=2);d.clip('b',body)
    d.path('M381 221 L381 182 Q385 151 418 151 Q450 151 452 174 Q461 189 443 205 L452 237 L391 247 Z',fill='#586a59')
    d.path('M385 223 Q416 236 451 227',stroke=PALE,width=8)
    d.ellipse(436,180,15,22,'#b56653',width=1)
    d.path('M448 176 L480 183 L448 194 Z',fill='#c5b885')
    d.eye(438,176,4)
    d.path('M353 246 Q288 217 260 260 L242 329 Q323 341 389 278 Z',fill='#9e8a64',width=2)
    rng=random.Random(45)
    for _ in range(130):
        x,y=rng.uniform(260,430),rng.uniform(242,340)
        d.path(f'M{x:.0f} {y:.0f} q8 10 15 0',stroke=DARK,width=1.2,extra='clip-path="url(#b)"')
    d.hatch('b',count=270)
    d.path('M306 346 L300 405 L282 416 M362 344 L375 405 L400 415 M299 405 L322 416 M374 405 L350 418',stroke='#867b61',width=4)
    d.branch();return d.finish()


def raptor(sci):
    d=Drawing()
    if sci=='Milvus milvus':
        # Forked tail and spread, fingered wings, deliberately different to the buzzard.
        d.path('M297 287 L201 443 L280 406 L352 448 L333 285 Z',fill='#9f7d56',width=2)
        d.path('M287 239 Q198 222 146 131 L86 62 L72 73 L95 138 L62 98 L55 113 L80 164 L42 142 L40 158 L90 213 Q151 286 288 291 Z',fill='#826c54',width=2)
        d.path('M331 242 Q426 219 481 126 L543 56 L557 69 L533 136 L570 95 L578 112 L551 169 L586 149 L592 165 L543 218 Q477 278 330 294 Z',fill='#826c54',width=2)
        d.path('M291 322 Q266 278 288 239 L297 174 Q307 143 330 161 L342 173 L348 190 L333 201 L337 271 Q351 309 323 329 Z',fill='#b39162',width=2)
        d.path('M297 190 L300 169 Q316 144 335 168 L337 190 Z',fill='#b5b4a7')
        d.path('M337 174 l19 6 l-10 11 l0 -7 l-10 -3 Z',fill=INK)
        for i in range(16):
            d.path(f'M{287-i*2} {252+i} Q178 262 {80+i*7} {139+i*6}',stroke='#cbc1a9',width=1.1)
            d.path(f'M{337+i*2} {252+i} Q452 248 {550-i*7} {139+i*6}',stroke='#cbc1a9',width=1.1)
        d.eye(326,173,3)
    else:
        body='M225 359 Q169 284 233 211 Q273 180 296 139 Q296 98 331 78 Q368 53 399 83 Q421 109 410 140 L397 165 Q452 221 425 302 Q388 380 296 386 Z'
        d.path('M246 338 L222 425 L335 425 L337 350 Z',fill=DARK,width=2)
        for y in (379,398,415):d.path(f'M223 {y} l106 0',stroke='#c7ba9b',width=7)
        d.path(body,fill='#9c8669',width=2);d.clip('b',body)
        d.ellipse(361,247,61,78,'#ddd4b5',stroke='none',extra='clip-path="url(#b)"')
        d.path('M306 186 Q229 180 207 290 L205 378 Q281 352 334 259 Q352 214 306 186 Z',fill='#645744',width=2)
        for i in range(16):d.path(f'M{236+i*5} 232 Q{261+i*4} 295 {206+i*6} 372',stroke='#a59a7e',width=1.2)
        d.hatch('b',count=650,colour='#564c3c')
        d.path('M404 115 Q444 117 443 136 L431 151 L432 134 L405 132 Z',fill='#8e8662',width=2)
        d.eye(391,109,6,iris='#b39c67')
        for x in (279,345):
            d.path(f'M{x} 375 L{x-3} 409 l-23 12 m23 -12 l25 12 m-22 -12 l-1 18',stroke='#b4a46f',width=5)
        d.branch()
    return d.finish()


def main():
    import cairosvg
    OUT.mkdir(parents=True,exist_ok=True);SRC.mkdir(parents=True,exist_ok=True)
    existing=set(p.stem for p in OUT.glob('*.png'))
    for sci,name,server in CATALOG:
        slug=sci.lower().replace(' ','_')
        if slug in existing:continue
        if sci in ('Streptopelia decaocto','Columba oenas','Columba livia'):svg=pigeon(sci)
        elif sci=='Strix aluco':svg=owl()
        elif sci in ('Delichon urbicum','Hirundo rustica'):svg=swallow(sci)
        elif sci in ('Branta canadensis','Anas platyrhynchos','Fulica atra','Porzana porzana','Gallinula chloropus'):svg=waterbird(sci)
        elif sci=='Ardea cinerea':svg=heron()
        elif sci=='Phasianus colchicus':svg=pheasant()
        elif sci in ('Milvus milvus','Buteo buteo'):svg=raptor(sci)
        else:svg=passerine(sci)
        (SRC/(slug+'.svg')).write_text(svg)
        cairosvg.svg2png(bytestring=svg.encode(),write_to=str(OUT/(slug+'.png')))
        from PIL import Image,ImageChops
        im=Image.open(OUT/(slug+'.png')).convert('RGB')
        bbox=ImageChops.difference(im,Image.new('RGB',im.size,'white')).getbbox()
        if bbox: im=im.crop((max(0,bbox[0]-8),max(0,bbox[1]-8),min(im.width,bbox[2]+8),min(im.height,bbox[3]+8)))
        im.save(OUT/(slug+'.png'),optimize=True)
    path=ROOT/'assets'/'manifest.json'
    old=json.loads(path.read_text())
    for sci,name,server in CATALOG:
        key=sci.lower();slug=key.replace(' ','_')
        if key not in old:
            old[key]={'name':server,'aliases':[name.lower(),server.lower()],
                      'file':slug+'.png','not_evidence':True,
                      'kind':'procedural decorative illustration' if (SRC/(slug+'.svg')).exists() else 'generated illustration crop'}
        old[key]['display_name']=name
    for alias,canonical in {'coloeus monedula':'corvus monedula','carduelis chloris':'chloris chloris',
        'parus caeruleus':'cyanistes caeruleus','parus ater':'periparus ater','parus caudatus':'aegithalos caudatus',
        'delichon urbica':'delichon urbicum'}.items():
        old[alias]={**old[canonical],'canonical_name':canonical}
    path.write_text(json.dumps(old,indent=2,ensure_ascii=False)+'\n')
    (ROOT/'assets'/'species_catalog.json').write_text(json.dumps(
        [{'scientific_name':sci,'display_name':name,'api_label':label} for sci,name,label in CATALOG],indent=2)+'\n')
    print('Catalogue:',len(CATALOG),'species; PNGs:',len(list(OUT.glob('*.png'))))

if __name__=='__main__':main()
