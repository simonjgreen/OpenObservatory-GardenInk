#!/usr/bin/env python3
"""Copy a local studio's paid outputs AND original prompts without making API calls.

Default is a read-only plan. --apply backs up replaced items first. Imports only
output/, species.json, STYLE_BRIEF.txt, reference/robin.png and a finished art ZIP.
Does not import a virtualenv, any source code, or a saved API key.
Stop generation and review/export operations before using this tool.
"""
from pathlib import Path
import argparse,contextlib,datetime,fcntl,hashlib,json,os,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
NAMES=['output','species.json','STYLE_BRIEF.txt','reference/robin.png','garden_ink_robin_art.zip']
BAD={'token.txt','.env','.secrets','openai-api-key'}
def selected(source):
    source=Path(source).expanduser().resolve()
    if not (source/'reference/robin.png').is_file() or not (source/'species.json').is_file():
        raise ValueError('Source must be the existing art_studio folder, not its output folder.')
    picks=[name for name in NAMES if (source/name).exists()]
    for name in picks:
        p=source/name
        entries=[p]+list(p.rglob('*')) if p.is_dir() else [p]
        for item in entries:
            if item.is_symlink():raise ValueError('Refusing symlink: '+str(item))
            if item.name in BAD or item.suffix.lower() in ('.pem','.key'):
                raise ValueError('Unexpected credential-shaped file: '+str(item))
    return source,picks
@contextlib.contextmanager
def locks(source,target):
    with contextlib.ExitStack() as stack:
        for root in (source,target):
            lock=root/'output/.studio.lock'
            lock.parent.mkdir(parents=True,exist_ok=True)
            f=stack.enter_context(lock.open('a'))
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Studio operation running: '+str(root)) from None
        yield

def import_art(source,target,apply=False,backup_root=None):
    source,picks=selected(source);target=Path(target).expanduser().resolve()
    if source==target or source in target.parents or target in source.parents:
        raise ValueError('Source and destination must be separate, non-nested studio folders.')
    if not (target/'studio.py').is_file():raise ValueError('Destination is not the project art_studio folder.')
    for name in picks:
        candidate=target/name
        chain=[candidate]+list(candidate.parents)
        if any(p.is_symlink() for p in chain if p==target or target in p.parents):
            raise ValueError('Refusing destination symlink: '+str(candidate))
    print('Source:',source);print('Target:',target)
    for name in picks:print('IMPORT',name)
    if not apply:
        print('Plan only. Add --apply to copy. Existing output and prompt files will be backed up.');return None
    with locks(source,target):
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup=Path(backup_root or ROOT/'local/import-backups')/('studio-'+stamp)
        backup.mkdir(parents=True,mode=0o700);backup.chmod(0o700)
        existed={}
        for name in picks:
            old=target/name;existed[name]=old.exists()
            if old.exists():
                save=backup/name;save.parent.mkdir(parents=True,exist_ok=True)
                if old.is_dir():shutil.copytree(old,save)
                else:shutil.copy2(old,save)
        installed=[]
        try:
            for name in picks:
                src=source/name;dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
                # Build before replacing. Operations are local; no HTTP/GPIO involved.
                stage=dest.with_name('.'+dest.name+'.import-'+stamp)
                if src.is_dir():shutil.copytree(src,stage,ignore=shutil.ignore_patterns('.studio.lock'))
                else:shutil.copy2(src,stage)
                installed.append(name)
                if name=='output':
                    # Preserve the directory and locked inode; do not create a second lock.
                    for old in dest.iterdir():
                        if old.name=='.studio.lock':continue
                        if old.is_dir():shutil.rmtree(old)
                        else:old.unlink()
                    for child in stage.iterdir():os.replace(child,dest/child.name)
                    stage.rmdir()
                else:
                    if dest.is_dir():shutil.rmtree(dest)
                    elif dest.exists():dest.unlink()
                    os.replace(stage,dest)
        except Exception:
            for name in reversed(installed):
                dest=target/name
                if name=='output':
                    for old in dest.iterdir():
                        if old.name=='.studio.lock':continue
                        if old.is_dir():shutil.rmtree(old)
                        else:old.unlink()
                    if existed[name]:shutil.copytree(backup/name,dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.studio.lock'))
                else:
                    if dest.is_dir():shutil.rmtree(dest)
                    elif dest.exists():dest.unlink()
                    if existed[name]:
                        saved=backup/name
                        if saved.is_dir():shutil.copytree(saved,dest)
                        else:shutil.copy2(saved,dest)
            raise
        info={'source':str(source),'files':picks,'replaced':existed,'time_utc':stamp,
              'api_calls':0,'note':'Prompts/reference imported to preserve request fingerprints; approval state unchanged.'}
        (backup/'IMPORT.json').write_text(json.dumps(info,indent=2)+'\n')
        print('Imported. Backup:',backup)
        print('No images generated, approved or deployed. Run art_studio/art.sh list to inspect state.')
        return backup

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path)
    p.add_argument('--target',type=Path,default=ROOT/'art_studio');p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    try:import_art(a.source,a.target,a.apply)
    except (OSError,ValueError,RuntimeError) as e:print('ERROR:',e,file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
