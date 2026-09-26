"""Inspect delivered STLs and completed OpenSCAD CSG intersection outputs.
Run export.sh and checks/run_collision.sh first. This is not physical qualification.
"""
from pathlib import Path
import hashlib, json, math, warnings
import numpy as np
import trimesh
warnings.filterwarnings('ignore', category=RuntimeWarning)
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def transform(rx=0,tz=0,local_y=0):
 a=math.radians(rx);c,s=math.cos(a),math.sin(a)
 M=np.array([[1,0,0,0],[0,c,-s,0],[0,s,c,tz],[0,0,0,1]],float)
 T=np.eye(4);T[1,3]=local_y
 return M@T
body=transform(100,10,94)
carrier=np.eye(4);carrier[2,3]=2.86
rear=transform(180,34)
transforms={'front':body,'carrier':body@carrier,'rear':body@rear,'stand':np.eye(4)}
report={'design':'Counterframe 7.3 E6','version':'1.0 engineering prototype','units':'mm',
 'source_sha256':sha(ROOT/'counterframe.scad'),'physically_print_or_fit_tested':False,
 'hardware_basis':'Published outlines and mounting holes; approximate component/connector envelopes.',
 'mesh_checks':{},'nominal_CSG_checks':{}}
placed=[]
for f in sorted((ROOT/'stl').glob('*.stl')):
 m=trimesh.load(f,force='mesh')
 bodies=len(m.split())
 row={'watertight':bool(m.is_watertight),'winding_consistent':bool(m.is_winding_consistent),
      'connected_bodies':bodies,'solid_volume_cm3':round(float(m.volume/1000),4),
      'print_bounds_mm':np.round(m.bounds,5).tolist(), 'print_extents_mm':np.round(m.extents,3).tolist(),
      'sha256':sha(f)}
 row['passed']=bool(m.is_watertight and m.is_winding_consistent and bodies==1 and m.volume>0 and m.bounds[0,2]>-0.001)
 report['mesh_checks'][f.name]=row
 if f.stem in transforms:
  m.apply_transform(transforms[f.stem]);placed.append(m)
allparts=trimesh.util.concatenate(placed)
report['assembly_envelope_excluding_power_cord_mm']=np.round(allparts.extents,3).tolist()
report['assembly_bounds_mm']=np.round(allparts.bounds,3).tolist()
# These are solid-mesh estimates, not slicer weight predictions.
report['solid_PLA_estimate']={'assumed_density_g_per_cm3':1.24,
 'solid_stand_mass_g':round(report['mesh_checks']['stand.stl']['solid_volume_cm3']*1.24,1),
 'note':'Density is an assumption; use the actual filament density and sliced extrusion for print estimates.'}
checks=['front_carrier','front_rear','carrier_rear','stand_case','hardware_carrier','hardware_rear',
        'ribbon_carrier','ribbon_rear','ribbon_front','wires_rear','wires_carrier','usb_stand']
for name in checks:
 f=ROOT/'checks'/f'{name}.stl';log=ROOT/'checks'/f'{name}.log'
 row={'passed':False}
 if f.exists():
  m=trimesh.load(f,force='mesh');v=abs(float(m.volume));row['overlap_volume_mm3']=round(v,6)
  if v<.001:
   row.update(passed=True,result='No volumetric overlap; zero-volume coplanar contacts only.')
  elif name in ['wires_rear','wires_carrier']:
   b=m.bounds
   inside=(b[0,0]>=5.79 and b[1,0]<=14.21 and b[0,1]>=-91.51 and b[1,1]<=-84.99 and b[0,2]>=5.0 and b[1,2]<=10.91)
   row.update(passed=bool(inside),result='Intentional nominal 0.10 mm diametral USB-jacket compression only.' if inside else 'UNEXPECTED INTERFERENCE',
              overlap_bounds_mm=np.round(b,5).tolist())
  else:row['result']='UNEXPECTED INTERFERENCE'
 elif log.exists() and 'Current top level object is empty.' in log.read_text():
  row.update(passed=True,overlap_volume_mm3=0,result='Empty intersection.')
 else:row['result']='Check missing, incomplete, or failed.'
 report['nominal_CSG_checks'][name]=row
report['FFC_route']={'overall_nominal_length_mm':50.0,'width_mm':25.5,'ways':50,
 'arch_rise_parameter_mm':10.0230859475,'analytic_minimum_radius_mm':6.6755,
 'peak_centerline_Z_mm':24.3754,'free_arch_X_span_mm':39.0,
 'self_crossing':'None: free-arch X is strictly monotone; straight contact ends extend outward.',
 'limitation':'Mechanical centreline design only. Match actual pitch, contacts, stiffeners and manufacturer bend limits. A short replacement cable may be needed.'}
report['limitations']=[
 'All checks are nominal CAD checks, not physical testing or a safety certification.',
 'Small components, solder, connector variants and real manufacturing tolerances are not exhaustively modelled.',
 'Electronics envelopes are not exact manufacturer STEP models.',
 'CSG checks are static; they do not simulate the entire insertion sequence, flexure forces or latch fatigue.',
 'The enclosure has not been sliced for a particular printer, printed, thermally tested, impact-tested or pull-tested.',
 'No claimed splash protection or anti-slip performance; all structural parts are PLA.'
]
report['all_reported_checks_pass']=all(r['passed'] for r in report['mesh_checks'].values()) and all(r['passed'] for r in report['nominal_CSG_checks'].values())
(ROOT/'validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'all_reported_checks_pass':report['all_reported_checks_pass'],
 'envelope_mm':report['assembly_envelope_excluding_power_cord_mm'],
 'stand_mass_g_assumed':report['solid_PLA_estimate']['solid_stand_mass_g'],
 'checks':{n:r['passed'] for n,r in report['nominal_CSG_checks'].items()}},indent=2))
if not report['all_reported_checks_pass']:raise SystemExit(1)
