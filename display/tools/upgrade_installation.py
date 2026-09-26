#!/usr/bin/env python3
"""Config-preserving v1 -> v2 upgrade. No third-party modules required."""
from __future__ import annotations
from dataclasses import asdict, fields
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile


def upgraded_settings(values: dict):
    from gardenink.config import Settings
    if not isinstance(values, dict):
        raise ValueError('Existing config is not a JSON object')
    known = {f.name for f in fields(Settings)}
    unknown = set(values)-known
    if unknown:
        raise ValueError('Unknown existing settings; no update made: '+', '.join(sorted(unknown)))
    merged = dict(values)
    # Preserve site, credentials, chosen score, timezone, artwork mode, hardware
    # orientation and timeouts. Only the requested edition policy is migrated.
    merged.update({'refresh_seconds':3600, 'heartbeat_seconds':3600,
                   'poll_seconds':3600, 'layout':'journal', 'rotate_layouts':False})
    merged['max_pages'] = max(64, int(values.get('max_pages',64)))
    merged.setdefault('fetch_budget_seconds',180)
    return Settings(**merged).validate()


def main(argv=None):
    args=argv or sys.argv[1:]
    validate_only=bool(args and args[0]=='--validate')
    if validate_only:args=args[1:]
    if len(args)!=2:raise ValueError('Expected source and destination directories')
    source, target=(Path(s).expanduser().resolve() for s in args)
    if source==target:raise ValueError('Extract the update into its own garden_ink_hourly directory first')
    if source in target.parents or target in source.parents:
        raise ValueError('The update folder must sit beside, not inside, the existing installation')
    if not (target/'gardenink/hardware.py').is_file() or not (target/'config.json').is_file():
        raise ValueError('Target is not a configured Garden Ink installation')
    sys.path.insert(0,str(source))
    cfg=upgraded_settings(json.loads((target/'config.json').read_text()))
    if validate_only:
        print('Existing configuration is compatible; site settings will be preserved.')
        return 0
    from gardenink.app import lock_display
    fd=lock_display()
    try:
        backup=target.with_name(target.name+'.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
        if backup.exists():raise ValueError('Backup name already exists; retry in a second')
        # A private parent is created before copying credential files beneath it.
        backup.mkdir(mode=0o700)
        shutil.copytree(target,backup,dirs_exist_ok=True,symlinks=True)
        backup.chmod(0o700)
        print('Backup:',backup)
        try:
            for item in source.iterdir():
                if item.name in ('config.json','token.txt','state','__pycache__','.git'):continue
                dest=target/item.name
                if item.name=='assets':
                    dest.mkdir(exist_ok=True)
                    for child in item.iterdir():
                        if child.name=='custom':continue
                        if child.is_dir():shutil.copytree(child,dest/child.name,dirs_exist_ok=True)
                        else:shutil.copy2(child,dest/child.name)
                elif item.is_dir():shutil.copytree(item,dest,dirs_exist_ok=True)
                else:shutil.copy2(item,dest)
            # Avoid stale source-dependent bytecode. Never follow directory symlinks.
            for folder in ('gardenink','tests','tools'):
                for root,dirs,files in os.walk(target/folder,followlinks=False):
                    if '__pycache__' in dirs:
                        cache=Path(root)/'__pycache__'
                        if not cache.is_symlink():shutil.rmtree(cache)
                        dirs.remove('__pycache__')
            for path in list(target.glob('*.sh'))+[target/'dashboard.py']:
                path.chmod(path.stat().st_mode|0o111)
            # An atomic replacement only after every file copy succeeded.
            from gardenink.storage import atomic_json
            atomic_json(target/'config.json',asdict(cfg))
        except Exception:
            print('Update interrupted. The service is stopped; recover the full backup at '+str(backup),file=sys.stderr)
            raise
        print('Installed Garden Ink 2.0.0: hourly; local today + trailing hour.')
        print('Preserved station URL, auth settings/token, custom art, orientation and state.')
        print('The bundled physical display driver is unchanged from the previous release.')
        return 0
    finally:os.close(fd)

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError) as exc:
        print('Upgrade stopped:',exc,file=sys.stderr)
        raise SystemExit(1)
