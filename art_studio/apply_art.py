#!/usr/bin/env python3
"""Install an approved artwork pack only; never changes code, config or cooldown."""
from __future__ import annotations
import argparse
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from PIL import Image


def atomic(path, raw):
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as f: f.write(raw)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def install(source, target):
    source = source.resolve(); target = target.expanduser().resolve()
    if not (target/'dashboard.py').is_file() or not (target/'gardenink').is_dir():
        raise ValueError('Target is not a Garden Ink installation.')
    info = json.loads((source/'PACK_INFO.json').read_text())
    patch = json.loads((source/'manifest_patch.json').read_text())
    new_catalogue = json.loads((source/'species_catalog.json').read_text())
    assets = target/'assets'
    for path in (assets, assets/'custom', assets/'manifest.json', assets/'species_catalog.json'):
        if path.is_symlink(): raise ValueError('Refusing a symlink in destination assets: '+str(path))
    if not assets.is_dir(): raise ValueError('Target assets directory does not exist.')
    images = {}
    for name, expected in info['files'].items():
        if not re.fullmatch(r'[a-z]+(?:_[a-z]+)+\.png', name): raise ValueError('Unsafe artwork filename.')
        src = source/'custom'/name
        if src.is_symlink(): raise ValueError('Refusing symlinked input artwork.')
        raw = src.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected: raise ValueError('Checksum mismatch: '+name)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.width*image.height > 12000000: raise ValueError('Invalid PNG: '+name)
            image.verify()
        images[name] = raw
    if not images: raise ValueError('No images in this pack.')
    for key, value in patch.items():
        if not re.fullmatch(r'[a-z]+(?: [a-z]+)+', key): raise ValueError('Unsafe scientific-name key.')
        if key.replace(' ','_')+'.png' not in images: raise ValueError('Missing custom file for '+key)
        if not isinstance(value.get('display_name'),str): raise ValueError('Missing display name.')
    for entry in new_catalogue:
        if entry['scientific_name'].casefold() not in patch: raise ValueError('Catalogue/manifest mismatch.')

    lockpath = '/tmp/garden-ink-spi0-ce0.lock'
    fd = os.open(lockpath, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Garden Ink is running. Stop it with ./service.sh stop before installing artwork.')
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + str(os.getpid())
        backup = target.parent/(target.name+'.art-backup-'+stamp)
        backup.mkdir(mode=0o700)
        custom = assets/'custom'; custom.mkdir(exist_ok=True)
        writes = {custom/name: raw for name, raw in images.items()}
        manifest_path = assets/'manifest.json'
        current = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        current.update(patch)
        writes[manifest_path] = (json.dumps(current,indent=2)+'\n').encode()
        cat_path = assets/'species_catalog.json'
        existing = json.loads(cat_path.read_text()) if cat_path.exists() else []
        merged = {item['scientific_name'].casefold(): item for item in existing}
        merged.update({item['scientific_name'].casefold(): item for item in new_catalogue})
        writes[cat_path] = (json.dumps(list(merged.values()),indent=2)+'\n').encode()
        old = {}
        for dest in writes:
            if dest.is_symlink(): raise ValueError('Refusing symlinked destination: '+str(dest))
            old[dest] = dest.read_bytes() if dest.exists() else None
            if old[dest] is not None:
                saved = backup/dest.relative_to(assets)
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(old[dest])
        (backup/'BACKUP_INFO.json').write_text(json.dumps({
            'target':str(target), 'new_files':[str(p.relative_to(assets)) for p,v in old.items() if v is None],
            'note':'Only replaced artwork and artwork metadata are backed up. No site credentials.'},indent=2))
        touched = []
        try:
            for dest, raw in writes.items():
                atomic(dest, raw); touched.append(dest)
        except Exception:
            for dest in reversed(touched):
                if old[dest] is None: dest.unlink(missing_ok=True)
                else: atomic(dest,old[dest])
            raise
        print('Installed %s artwork filenames for %s approved species.' % (len(images), info['species_count']))
        print('Full studio catalogue: '+str(info['complete_catalogue']))
        print('Backup: '+str(backup))
        print('Application, configuration, credentials and hourly cooldown are unchanged.')
        print('Next: cd "%s" && ./run.sh --preview && ./service.sh start' % target)
    finally:
        os.close(fd)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('target',type=Path,nargs='?',default=Path.home()/'garden_ink')
    args=p.parse_args()
    install(Path(__file__).resolve().parent,args.target)

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);sys.exit(1)
