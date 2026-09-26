include <../counterframe.scad>
difference(){ hardware_native(); union(){panel_native();
 pcb(pi_pos,pi_size,pi_z,pi_holes,2.75,[1,1,1]);
 pcb(hat_pos,hat_size,hat_z,hat_holes,3,[1,1,1]);
 pcb(adapter_pos,adapter_size,adapter_z,adapter_holes,3,[1,1,1]);} }
