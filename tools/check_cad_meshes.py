#!/usr/bin/env python3
"""Recheck printable meshes without replacing the original 2026-09-23 report."""
from pathlib import Path
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
def main():
    import trimesh
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'local/cad-mesh-check.json');a=p.parse_args()
    rows=[]
    for f in sorted((ROOT/'hardware/counterframe/stl').glob('*.stl')):
        m=trimesh.load(f,force='mesh');bodies=len(m.split())
        rows.append({'file':f.name,'watertight':bool(m.is_watertight),
                     'consistent_winding':bool(m.is_winding_consistent),'connected_bodies':bodies,
                     'extents_mm':[round(float(x),4) for x in m.extents],
                     'positive_volume':bool(m.volume>0),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
                     'pass':bool(m.is_watertight and m.is_winding_consistent and bodies==1 and m.volume>0)})
    report={'scope':'Mesh validity only; not fit, stress, cable bends, thermal or impact testing.',
            'files':rows,'pass':len(rows)==9 and all(x['pass'] for x in rows)}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 0 if report['pass'] else 1
if __name__=='__main__':raise SystemExit(main())
