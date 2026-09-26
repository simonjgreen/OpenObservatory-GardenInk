#!/usr/bin/env python3
"""Run separated suites against this checkout. No real API, credentials or GPIO."""
from pathlib import Path
import argparse, json, os, re, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[1]
SUITES=[('display',ROOT/'display/tests'),('autoart',ROOT/'tests/autoart'),
        ('art-studio',ROOT/'tests/studio'),('project',ROOT/'tests/project')]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--log-dir',type=Path,default=ROOT/'local/test-results')
    a=p.parse_args();a.log_dir.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'PYTHONPATH':str(ROOT/'display'),'PYTHONDONTWRITEBYTECODE':'1'}
    # Do not expose even an incidental workstation credential to tests.
    for key in list(env):
        if any(s in key.upper() for s in ('API_KEY','API_TOKEN','AUTH_TOKEN')):
            env.pop(key,None)
    results=[]
    for name,directory in SUITES:
        started=time.monotonic()
        command=[sys.executable,'-m','unittest','discover','-s',str(directory),'-v']
        print('\n=== '+name+' ===',flush=True)
        run=subprocess.run(command,cwd=ROOT/'display' if name=='display' else ROOT,
                           env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (a.log_dir/(name+'.txt')).write_text(run.stdout)
        print('\n'.join(run.stdout.splitlines()[-9:]))
        n=re.search(r'Ran (\d+) tests?',run.stdout)
        results.append({'suite':name,'tests':int(n.group(1)) if n else None,
                        'returncode':run.returncode,'seconds':round(time.monotonic()-started,3)})
    report={'python':sys.version,'suites':results,
            'tests':sum(r['tests'] or 0 for r in results),
            'passed':all(r['returncode']==0 for r in results),
            'live_api_calls':False,'hardware_driven':False}
    (a.log_dir/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print('\n'+json.dumps(report,indent=2))
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
