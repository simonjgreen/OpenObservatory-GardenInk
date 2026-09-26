from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).resolve().parents[1]
expressions={
 'glass':'color("grey") translate([panel_dx,0,front_t+panel_t/2]) cube([panel_w,panel_h,panel_t],center=true);',
 'pi_pcb':'pcb(pi_pos,pi_size,pi_z,pi_holes,2.75,[.1,.3,.2]);',
 'hat_pcb':'pcb(hat_pos,hat_size,hat_z,hat_holes,3,[.1,.2,.4]);',
 'adapter_pcb':'pcb(adapter_pos,adapter_size,adapter_z,adapter_holes,3,[.1,.2,.4]);',
 'fpc':'ribbon_path(fpc_points,25.5,.15);',
 'ffc':'ribbon_path(ffc_points,25.5,.18);',
 'components':'''difference(){ hardware_native(); union(){panel_native();
 pcb(pi_pos,pi_size,pi_z,pi_holes,2.75,[1,1,1]);
 pcb(hat_pos,hat_size,hat_z,hat_holes,3,[1,1,1]);
 pcb(adapter_pos,adapter_size,adapter_z,adapter_holes,3,[1,1,1]);} }''',
 'wires':'wires_native();',
 'power_external':'power_external();',
}
def run(k,v):
 f=root/'checks'/f'render_{k}.scad'; f.write_text('include <../counterframe.scad>\n'+v+'\n')
 with open(root/'checks'/f'render_{k}.log','w') as log:
  r=subprocess.run(['openscad','-D','part="none"','-o',str(root/'reference'/f'{k}.stl'),str(f)],stdout=log,stderr=log)
  if r.returncode: raise RuntimeError(k)
with ThreadPoolExecutor(max_workers=3) as ex:
 list(ex.map(lambda kv:run(*kv), expressions.items()))
