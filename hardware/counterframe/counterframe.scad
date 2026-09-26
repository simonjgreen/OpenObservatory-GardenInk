/*
COUNTERFRAME / 7.3 E6 / v1.0 engineering prototype
Generated design, 2026. CC0-1.0 for this code and generated enclosure meshes.
Manufacturer drawings and trademarks are not included in that dedication.
Units: mm. Four structural parts, no screws, glue, inserts, magnets or elastomers.
Read README.md before printing: the glass and FPC are NOT press-fit parts.

Hardware baseline, checked 2026-09-23:
- Waveshare 7.3inch e-Paper HAT (E), 6 colours, NOT (F)/(G).
  Glass 170.2 x 111.2 x 0.91; active 160 x 96; active offsets 5.1 / 4.7.
  Dedicated HAT 65 x 30.5, 58 x 23 hole pitch, 3 mm holes.
  FPC adapter 45 x 21, 38 x 14 hole pitch, 3 mm holes.
- Pi Zero envelope 65 x 30; 58 x 23 holes, diameter 2.75.
- Component HEIGHTS, cable jacket and glass thickness require measurement.
- FFC routing model: 50 mm OVERALL, 50-way, matching kit contact orientation.
  A short matching replacement FFC is required if the kit cable is longer.

Source drawing URLs and assumptions in README.md.
Coordinates looking INSIDE FROM THE REAR: X right, Y up, Z toward the rear.
Front is Z=0. Bonded panel FPC exits +X (left edge when looking at the screen).
part='assembly' is a visual assembly, NOT a single printable STL.
Use the four part selectors to export the manufacturing STLs.
*/

/* [Output] */
part = "assembly"; // [assembly,exploded,front,carrier,rear,stand,coupon_pins,coupon_holes,coupon_latch,coupon_socket,release_key,section,hardware,ribbon,wires]
show_hardware = true;
show_cables = true;
quality = 48;
$fn = quality;

/* [Measured hardware - verify before print] */
panel_w = 111.2;
panel_h = 170.2;
panel_t = 0.91;
active_w = 96;
active_h = 160;
// Difference between panel and active-area centres in portrait orientation.
panel_dx = 2.9;
panel_xy_clear = 0.30; // PER SIDE, not total
panel_z_clear = 0.15;  // capture clearance; never clamp glass by closing case
pcb_t = 1.60;
pi_peg_d = 2.50;
hat_peg_d = 2.70;
pcb_capture_clear = 0.15;
cable_d = 3.40;
cable_grip = 0.10;    // diametral squeeze on USB jacket only; measure first
fpc_radius = 4.50;    // design assumption, NOT a manufacturer-certified limit

/* [Case] */
case_w = 134;
case_h = 188;
edge_depth = 9;
case_depth = 34;
wall = 2.2;
front_t = 1.8;
corner_r = 8;
carrier_t = 2.2;
fit = 0.30;
lean = 10;
base_w = 142;
base_d = 108;
base_t = 8;
base_cy = -26;
bottom_lift = 10;

/* [Hidden] */
eps=0.025;
carrier_z=front_t+panel_t+panel_z_clear;
carrier_top=carrier_z+carrier_t;
pi_pos=[-44,-66];
pi_size=[65,30];
pi_z=carrier_top+3;
hat_pos=[-37,-32.5];
hat_size=[30.5,65];
hat_z=carrier_top+9; // preserves stock underside female GPIO connector
adapter_pos=[32.5,-22.5];
adapter_size=[21,45];
adapter_z=carrier_top+4;
pi_holes=[for(x=[3.5,61.5],y=[3.5,26.5]) [pi_pos[0]+x,pi_pos[1]+y]];
hat_holes=[for(x=[4,27],y=[3.5,61.5]) [hat_pos[0]+x,hat_pos[1]+y]];
adapter_holes=[for(x=[3.5,17.5],y=[3.5,41.5]) [adapter_pos[0]+x,adapter_pos[1]+y]];
carrier_fix=[for(x=[-60,60],y=[-88.5,88.5]) [x,y]];
usb_x=pi_pos[0]+54;
usb_z=7.4;
frame_inner_x=case_w/2-wall;
carrier_half=case_w/2-wall-fit;
back_w=104;
back_h=148;
// Smooth S-bend of USB jacket, R8 design radius; the split saddle follows it.
// This is a cable envelope assumption, not a cable manufacturer's rating.
usb_R=8;
usb_start_y=-79.5;
usb_start_z=12.8;
usb_a=acos(1-(usb_start_z-usb_z)/(2*usb_R));
usb_mid_y=usb_start_y-usb_R*sin(usb_a);
usb_mid_z=usb_start_z-usb_R*(1-cos(usb_a));
usb_internal_points=concat(
    [for(a=[0:usb_a/8:usb_a]) [usb_x,usb_start_y-usb_R*sin(a),usb_start_z-usb_R*(1-cos(a))]],
    [for(a=[usb_a:-usb_a/8:0]) [usb_x,usb_mid_y-usb_R*(sin(usb_a)-sin(a)),
                                      usb_mid_z-usb_R*(cos(a)-cos(usb_a))]]);
usb_exit_y=usb_start_y-2*usb_R*sin(usb_a);
// R8 sweep turns the cable rearwards under the stand BEFORE it reaches the worktop.
usb_exit_points=[for(a=[0:5:90+lean]) [usb_x,usb_exit_y-usb_R*sin(a),usb_z+usb_R*(1-cos(a))]];
usb_path=concat(usb_internal_points,usb_exit_points);
usb_last=usb_exit_points[len(usb_exit_points)-1];
usb_world_y=cos(90+lean)*(usb_last[1]+case_h/2)-sin(90+lean)*usb_last[2];
usb_world_z=bottom_lift+sin(90+lean)*(usb_last[1]+case_h/2)+cos(90+lean)*usb_last[2];

assert(panel_w>active_w && panel_h>active_h,"Panel must exceed active area");
assert(panel_z_clear>=0.05,"Do not force-clamp the glass");
assert(case_depth>=33,"Default GPIO lead boots require 33+ mm; recheck envelopes");
assert(case_w>=134,"FPC loop needs the default right-side clearance");
assert(pi_peg_d<2.75 && hat_peg_d<3,"Locators must clear PCB holes, not wedge them");

module rr2(w,h,r=3) { offset(r=r) square([w-2*r,h-2*r],center=true); }
module rr(w,h,z0,hz,r=3) { translate([0,0,z0]) linear_extrude(hz) rr2(w,h,r); }
module box_at(x,y,z,w,h,d) { translate([x,y,z]) cube([w,h,d]); }
module rod(a,b,r=1) { hull() {translate(a) sphere(r=r,$fn=16);translate(b) sphere(r=r,$fn=16);} }
module path_tube(points,r=1) { for(i=[0:len(points)-2]) rod(points[i],points[i+1],r); }
module ribbon_path(points,width=25.5,t=0.18) {
    // All points share Y=0. The ribbon bends ONLY through thickness, not edgewise.
    for(i=[0:len(points)-2]) hull() {
        translate(points[i]) cube([t,width,t],center=true);
        translate(points[i+1]) cube([t,width,t],center=true);
    }
}
module standing() {
    translate([0,0,bottom_lift]) rotate([90+lean,0,0]) translate([0,case_h/2,0]) children();
}
module plate_ring(w,h,iw,ih,z,t,r=5) {
    difference(){rr(w,h,z,t,r);rr(iw,ih,z-eps,t+2*eps,1);}
}
module peg(p,zseat,d,h=2.8,base=5.2) {
    translate([p[0],p[1],carrier_top-eps]) {
        cylinder(h=zseat-carrier_top+eps,d1=base+1.8,d2=base);
        translate([0,0,zseat-carrier_top]) cylinder(h=h-0.8,d=d);
        translate([0,0,zseat-carrier_top+h-0.8]) cylinder(h=.8,d1=d,d2=d-.7);
    }
}
module case_envelope(c=0) {
    union(){
        rr(case_w+2*c,case_h+2*c,-c,edge_depth+2*c,corner_r+c);
        hull(){
            rr(case_w+2*c,case_h+2*c,edge_depth-c,.8,corner_r+c);
            rr(back_w+2*c,back_h+2*c,case_depth-.8, .8+c,10+c);
        }
    }
}
module rear_outer(c=0) {
    hull(){
        rr(case_w+2*c,case_h+2*c,edge_depth-c,.8,corner_r+c);
        rr(back_w+2*c,back_h+2*c,case_depth-.8,.8+c,10+c);
    }
}
module rear_inner() {
    hull(){
        rr(case_w-2*wall,case_h-2*wall,edge_depth-1,1,corner_r-wall);
        rr(back_w-2*wall,back_h-2*wall,case_depth-wall-.8,.8,10-wall);
    }
}
module cable_bore(radius_extra=0) {
    // The exit is split between shells; no need to thread a USB plug through a hole.
    path_tube(usb_path,(cable_d-cable_grip)/2+radius_extra);
}
module usb_clearance() {
    box_at(usb_x-3.1,-96,usb_z-.2,6.2,12,5);
    cable_bore(.40);
}
module front_native() {
    difference(){
        union(){
            // Flat exterior face, 0.6 mm outside edge bevel; printable face down.
            hull(){rr(case_w-1.2,case_h-1.2,0,.10,corner_r-.6);
                   rr(case_w,case_h,.6,edge_depth-.6,corner_r);}
        }
        // Main interior.
        rr(case_w-2*wall,case_h-2*wall,front_t,edge_depth+3,corner_r-wall);
        // The aperture, centred on the ACTIVE AREA, not on the raw glass.
        rr(active_w+.8,active_h+.8,-eps,front_t+2*eps,.45);
        // Two concealed stand-detent pockets, below the image, not through the face.
        for(s=[-1,1]) box_at(s*27.5-2.4,-91.8,-eps,4.8,3.4,1.05);
        // Carrier windows and rear-shell latch windows are separate.
        for(s=[-1,1],cy=[-55,55])
            box_at(s>0?frame_inner_x-eps:-case_w/2-eps,cy+6,carrier_z+.50,
                   wall+2*eps,8,carrier_t+.85);
        for(s=[-1,1],cy=[-38,38])
            box_at(s>0?frame_inner_x-eps:-case_w/2-eps,cy+5,6.1,
                   wall+2*eps,8,2.0);
        usb_clearance();
    }
    // Glass lateral guides. Separate broad blocks, no point-loaded conical glass pegs.
    difference(){
        union(){
            for(s=[-1,1],yy=[-67,67])
                box_at(panel_dx+s*(panel_w/2+panel_xy_clear)-(s<0?2:0),yy-9,
                       front_t-eps,2,18,panel_t+panel_z_clear-.075);
            for(s=[-1,1],xx=[-32,32])
                box_at(xx-10,s*(panel_h/2+panel_xy_clear)-(s<0?2:0),
                       front_t-eps,20,2,panel_t+panel_z_clear-.075);
        }
        // Lead-ins are intentionally broad; do not push on the FPC edge.
    }
    for(p=carrier_fix) translate([p[0],p[1],front_t-eps]) {
        cylinder(h=carrier_z-front_t+eps,d=6.0);
        translate([0,0,carrier_z-front_t]) cylinder(h=2.8,d1=3.1,d2=2.6);
    }
}
module carrier_hook(s,cy) {
    // A 26 mm in-plane leaf. Small assembly deflection; nearly unloaded when latched.
    x=s>0?carrier_half-1.2:-carrier_half;
    box_at(x,cy-13,carrier_z,1.2,26,carrier_t);
    // Lead-in ramp in Z, retaining shoulder at rear of keeper.
    if(s>0) hull(){
        box_at(carrier_half-.2,cy+7,carrier_z+.35,.2,5,.12);
        box_at(carrier_half-.2,cy+7,carrier_z+1.25,1.15,5,carrier_t-1.25);
    } else mirror([1,0,0]) carrier_hook_head(cy);
}
module carrier_hook_head(cy) {
    hull(){box_at(carrier_half-.2,cy+7,carrier_z+.35,.2,5,.12);
           box_at(carrier_half-.2,cy+7,carrier_z+1.25,1.15,5,carrier_t-1.25);}
}
module carrier_native() {
    difference(){
        union(){
            plate_ring(2*carrier_half,case_h-2*wall-2*fit,102,164,carrier_z,carrier_t,5);
            // Skeletal crossbars: air gap over glass, loads return to the outside ring.
            for(y=[-62.5,-39.5]) box_at(-61,y-2.5,carrier_z,122,5,carrier_t);
            for(x=[-33,-10]) box_at(x-2.5,-42,carrier_z,5,131,carrier_t);
            for(x=[36,50]) box_at(x-2,-84,carrier_z,4,170,carrier_t);
            // USB jacket support in the inactive bottom border.
            box_at(usb_x-5,-91.5,carrier_z,10,7.5,carrier_t);
        }
        for(p=carrier_fix) translate([p[0],p[1],carrier_z-eps])
            cylinder(h=carrier_t+.1,d=3.55);
        // Right-side protected U bend of the panel's bonded FPC.
        box_at(56,-17,carrier_z-1,15,34,carrier_t+3);
        // Release leaf slots; leave 2 mm root connection.
        for(s=[-1,1],cy=[-55,55]) {
            box_at(s>0?carrier_half-2.5:-carrier_half,cy-11,carrier_z-eps,
                   2.5,25.1,carrier_t+.1);
        }
    }
    for(s=[-1,1],cy=[-55,55]) carrier_hook(s,cy);
    for(p=pi_holes) peg(p,pi_z,pi_peg_d);
    for(p=hat_holes) peg(p,hat_z,hat_peg_d);
    for(p=adapter_holes) peg(p,adapter_z,hat_peg_d);
    // FFC fences do not squeeze the ribbon; 30 mm clear lane for 25.5 mm cable.
    for(y=[-16.5,15]) {
        // Bed-level tie to the adapter rail; the tall fence stops before its PCB.
        box_at(2,y,carrier_z,36,1.5,carrier_t);
        box_at(2,y,carrier_top-eps,27.5,1.5,5.5);
    }
    // USB strain-relief lower saddle. Only USB jacket may be lightly gripped.
    difference(){
        box_at(usb_x-4.2,-91.5,carrier_top-eps,8.4,6.5,usb_z-carrier_top+eps);
        cable_bore();
    }
}
module rear_latch(s,cy) {
    x=s>0?frame_inner_x-1.6:-frame_inner_x+.4;
    box_at(x,cy-13,6.1,1.2,26,3.1);
    if(s>0) hull(){
        box_at(frame_inner_x-.5,cy+6,6.1,.2,5,.15);
        box_at(frame_inner_x-.5,cy+6,7.15,.95,5,.65);
    } else mirror([1,0,0]) rear_latch_head(cy);
}
module rear_latch_head(cy) {
    hull(){box_at(frame_inner_x-.5,cy+6,6.1,.2,5,.15);
           box_at(frame_inner_x-.5,cy+6,7.15,.95,5,.65);}
}
module board_capture(p,zseat) {
    z0=zseat+pcb_t+pcb_capture_clear;
    // An annular collar supports ONLY the plated mounting-hole land.
    difference(){
        union(){
            translate([p[0],p[1],z0]) cylinder(h=case_depth-wall-z0+.5,d=5.2);
            translate([p[0],p[1],case_depth-wall-4]) cylinder(h=5,d1=5.2,d2=9);
        }
        translate([p[0],p[1],z0-eps]) cylinder(h=3.7,d=3.5);
    }
}
module rear_native() {
    difference(){
        union(){
            difference(){rear_outer();rear_inner();}
            difference(){
                plate_ring(case_w-2*wall-.8,case_h-2*wall-.8,
                           case_w-2*wall-4.0,case_h-2*wall-4.0,6.1,4.2,5);
                for(s=[-1,1],cy=[-38,38])
                    box_at(s>0?frame_inner_x-2.9:-frame_inner_x-.1,cy-11,5.8,3,25.2,5.0);
                // No skirt crosses the fragile bonded FPC loop.
                box_at(56,-18,5,15,36,6);
                usb_clearance();
                // Entire lower-jaw envelope, not just the jacket, clears the skirt.
                box_at(usb_x-4.5,-95,5.8,9,12,4.6);
            }
            for(s=[-1,1],cy=[-38,38]) rear_latch(s,cy);
            intersection(){
                rear_outer();
                union(){
                    for(p=pi_holes) board_capture(p,pi_z);
                    for(p=hat_holes) board_capture(p,hat_z);
                    for(p=adapter_holes) board_capture(p,adapter_z);
                    // Keeper-frame axial hard stops; no force on the display glass.
                    for(p=carrier_fix) translate([p[0],p[1],carrier_top+.15])
                        cylinder(h=12,d=6);
                }
            }
            // Rear-to-carrier hard stop posts must reach the low keeper plane.
            for(p=carrier_fix) translate([p[0],p[1],carrier_top+.15])
                cylinder(h=edge_depth-carrier_top+.7,d=5.4);
            // Upper USB saddle, connected into lower rim.
            difference(){
                box_at(usb_x-4.2,-91.5,usb_z,8.4,6.5,3.5);
                cable_bore();
            }
        }
        // Relief for the four FRONT locator tips within keeper hard stops.
        for(p=carrier_fix) translate([p[0],p[1],carrier_top+.1]) cylinder(h=3.5,d=3.55);
        // Breathing slots on rear, away from direct upward-facing openings.
        for(y=[-69,-55,55,69],x=[-21,0,21])
            box_at(x-7,y-1.2,case_depth-5,14,2.4,7);
        // Clearance outside the jaw: the housing must NOT clamp the jacket here.
        intersection(){
            cable_bore(.45);
            box_at(usb_x-5,-99,0,10,7.45,20);
        }
        // Relief in the lower split cable exit; preserves the saddle's grip section.
        translate([usb_x,-96,usb_z]) rotate([-90,0,0]) cylinder(h=2.3,d=cable_d+.8);
    }
}
module detent_head() {
    // X extrusion of a ramp, tip pointing into a front bezel pocket.
    translate([-29,-91.35,-.35]) rotate([0,90,0])
        linear_extrude(3) polygon([[0,0],[-.9,0],[-.9,1.35],[0,2.65]]);
}
module stand_native() {
    difference(){
        union(){
            // A low, solid PLA plinth provides mass without metal ballast.
            translate([0,base_cy,0]) hull(){
                rr(base_w-1.2,base_d-1.2,0,.15,13);
                rr(base_w,base_d,.7,base_t-1.4,13);
                rr(base_w-1.4,base_d-1.4,base_t-.7,.7,12.3);
            }
            // Cradle front lip, plus two broad rear buttresses.
            standing() box_at(-65,-96,-3,130,12,4);
            for(x=[-48,48]) hull(){
                translate([x,-29,base_t-.5]) cube([21,25,1],center=true);
                standing() box_at(x-9,-92,8,18,22,23);
            }
        }
        standing() case_envelope(fit);
        // Split outlet emerges into an open downward-facing under-base raceway.
        // Smooth 8 mm cable tunnel: no connector must be passed through it.
        box_at(usb_x-4.2,base_cy-base_d/2-1,-eps,8.4,base_d/2+29,5.3);
        hull(){
            translate([usb_x,-14,4]) rotate([90,0,0]) cylinder(h=5,d=8.4);
            translate([usb_x,-4,8]) rotate([90,0,0]) cylinder(h=5,d=8.4);
        }
        standing() path_tube(usb_exit_points,cable_d/2+.60);
        // Leaf isolation windows in the front lip.
        for(s=[-1,1]) standing()
            box_at(s>0?24:-50,-92,-4,26,4,5);
    }
    // Two horizontal PLA detent leaves. Local supports recommended below these tips.
    for(s=[-1,1]) standing() {
        if(s<0) {
            box_at(-52,-91.4,-1.55,26,2.8,1.2);
            detent_head();
        } else mirror([1,0,0]) {
            box_at(-52,-91.4,-1.55,26,2.8,1.2);
            detent_head();
        }
    }
}

// ---------- Non-printing hardware envelopes ----------
module pcb(pos,size,z,holes,hole_d,col) {
    color(col) difference(){
        translate([pos[0]+size[0]/2,pos[1]+size[1]/2,z]) linear_extrude(pcb_t)
            rr2(size[0],size[1],2.5);
        for(p=holes) translate([p[0],p[1],z-eps]) cylinder(h=pcb_t+.1,d=hole_d);
    }
}
module panel_native() {
    color([.2,.24,.25]) translate([panel_dx,0,front_t+panel_t/2]) cube([panel_w,panel_h,panel_t],center=true);
    color([.91,.91,.87]) translate([0,0,front_t-.03]) cube([active_w,active_h,.12],center=true);
}
module hardware_native() {
    panel_native();
    pcb(pi_pos,pi_size,pi_z,pi_holes,2.75,[.10,.38,.26]);
    pcb(hat_pos,hat_size,hat_z,hat_holes,3,[.08,.25,.48]);
    pcb(adapter_pos,adapter_size,adapter_z,adapter_holes,3,[.08,.25,.48]);
    color([.13,.15,.16]) {
        box_at(-20,-56,pi_z+pcb_t,12,12,1.7);
        box_at(-37,-41.6,pi_z+pcb_t,51,5.2,2.5); // Pi header black plastic
        box_at(-12,-25.4,hat_z-8.5,5.2,50.8,8.5);    // HAT's existing female header
    }
    color([.73,.75,.76]) {
        box_at(-45.5,-58,pi_z+pcb_t,13,13,1.5); // microSD envelope
        for(x=[pi_pos[0]+41.4,usb_x]) box_at(x-4,-67,pi_z+pcb_t,8,5.8,2.8);
        box_at(pi_pos[0]+12.4-5.8,-67,pi_z+pcb_t,11.6,7.6,3.3);
    }
    color([.82,.83,.79]) {
        box_at(-10,-13.5,hat_z+pcb_t,3.5,27,2.4); // HAT FFC
        box_at(-37,-10,hat_z+pcb_t,6,20,5.8);     // HAT SPI
        box_at(32.5,-13.5,adapter_z+pcb_t,3.5,27,2.4);
        box_at(50,-13.5,adapter_z+pcb_t,3.5,27,2.4);
    }
    color([.13,.15,.16]) {
        box_at(usb_x-4.8,-80,pi_z+pcb_t+.2,9.6,14,5.6);
        box_at(-49,-10,hat_z+pcb_t,12,20,6);
        // Female jumper housings: realistic tall keep-out, not a flush connector.
        box_at(-12,-41.8,pi_z+pcb_t+2.5,23,5.5,14);
    }
}
fpc_z=front_t+panel_t;
fpc_edge=panel_dx+panel_w/2;
fpc_points=concat([[fpc_edge,0,fpc_z],[fpc_edge+1,0,fpc_z]],
    [for(a=[0:5:180]) [fpc_edge+1+fpc_radius*sin(a),0,fpc_z+fpc_radius*(1-cos(a))]],
    [[50.7,0,fpc_z+2*fpc_radius]]);
ffc_za=adapter_z+pcb_t+1.05;
ffc_zh=hat_z+pcb_t+1.05;
// Monotone-X arch: no crossing or overlapping folds. Nominal total length 50 mm.
// 2.5 mm straight seated end at each socket, plus 45 mm free arch.
// Rise solved for the nominal 39 mm mouth-to-mouth X span and 5 mm height change.
// Smooth centreline minimum radius ~6.68 mm; confirm suitability of actual cable.
ffc_arch_rise=10.0230859475;
ffc_points=concat([[35,0,ffc_za]],
    [for(t=[0:1/80:1]) [32.5-39*t,0,
        ffc_za+(ffc_zh-ffc_za)*(3*t*t-2*t*t*t)+ffc_arch_rise*pow(sin(180*t),2)]],
    [[-9,0,ffc_zh]]);
module ribbons_native() {
    color([.84,.47,.10]) ribbon_path(fpc_points,25.5,.15);
    color([.85,.87,.87]) ribbon_path(ffc_points,25.5,.18);
}
module wires_native() {
    for(i=[0:7]) color(i==0?[.72,.17,.13]:i==1?[.10,.12,.14]:[.27,.40,.51])
        path_tube([[-10+i*2.54,-38.5,26],[-10+i*2.54,-34.5,27.4],
                   [-44.5+i*.1,-34.5,27],[-48+i*.32,-17,24],
                   [-51.0,(-7+i*2),21],[-48,(-7+i*2),21]],.42);
    color([.13,.14,.15]) path_tube(usb_path,cable_d/2);
}
module power_external() {
    color([.15,.16,.17]) path_tube([[usb_x,usb_world_y,usb_world_z],
        [usb_x,-83,usb_world_z],[usb_x,-101,usb_world_z],[25,-116,usb_world_z]],cable_d/2);
}
module display_art() {
    // Geometry-only demonstration content; not an electronics/software deliverable.
    color([.17,.22,.23]) translate([0,61,front_t-.16]) rotate([0,180,0])
        linear_extrude(.04) text("WEDNESDAY",size=4,halign="center",font="Liberation Sans:style=Bold");
    color([.17,.22,.23]) translate([0,39,front_t-.16]) rotate([0,180,0])
        linear_extrude(.04) text("23",size=21,halign="center",font="Liberation Sans:style=Bold");
    color([.63,.26,.17]) translate([0,28,front_t-.16]) rotate([0,180,0])
        linear_extrude(.04) text("SEPTEMBER",size=3.5,halign="center",font="Liberation Sans");
    color([.28,.38,.27]) box_at(-34,16,front_t-.17,68,.45,.06);
    color([.28,.38,.27]) translate([0,-7,front_t-.16]) rotate([0,180,0])
        linear_extrude(.04) text("A little everyday",size=4.8,halign="center",font="Liberation Serif");
    color([.28,.38,.27]) translate([0,-15,front_t-.16]) rotate([0,180,0])
        linear_extrude(.04) text("inspiration.",size=4.8,halign="center",font="Liberation Serif:style=Italic");
    for(i=[0:5]) color([[.08,.09,.10],[.95,.95,.90],[.83,.68,.10],[.69,.17,.13],[.2,.38,.22],[.16,.28,.51]][i])
        translate([-25+i*10,-53,front_t-.18]) cylinder(h=.04,r=3.2);
}
module assembly(explode=0) {
    color([.76,.78,.74]) stand_native();
    if(show_cables) power_external();
    standing(){
        color([.85,.86,.81]) translate([0,0,-explode]) front_native();
        if(show_hardware) {hardware_native();display_art();}
        color([.43,.50,.48]) translate([0,0,explode*.5]) carrier_native();
        if(show_cables) {ribbons_native();wires_native();}
        color([.72,.75,.72]) translate([0,0,explode*1.8]) rear_native();
    }
}
// Calibration coupons are separate prints, NOT needed in the final enclosure.
module coupon_pins() {
    rr(65,22,0,2,3);
    for(i=[0:4]) translate([-24+i*12,0,2]) {
        cylinder(h=3,d=5.2);translate([0,0,3]) cylinder(h=2,d=2.4+i*.1);
        translate([0,0,5]) cylinder(h=.8,d1=2.4+i*.1,d2=1.8+i*.1);
    }
}
module coupon_holes() {
    difference(){rr(65,22,0,pcb_t,3);
        for(i=[0:4]) translate([-24+i*12,0,-eps]) cylinder(h=pcb_t+.1,d=i<3?2.75:3);}
}
module coupon_latch() {
    union(){box_at(0,0,0,34,8,2.2);box_at(0,0,0,5,19,2.2);
            box_at(3,17.8,0,28,1.2,2.2);
            hull(){box_at(27,18.8,.4,4,.2,.1);box_at(27,18.8,1.3,4,1.1,.9);}}
}
module coupon_socket() {
    difference(){box_at(0,0,0,34,23,4.5);box_at(-1,-1,1,36,20.3,5);
                box_at(26,19,2.2,6,5,1.3);}
}

// Optional all-PLA latch release tool. Press into side windows; do not lever glass.
module release_key() {
    translate([0,-10,0]) rr(18,34,0,2.2,5);
    hull(){box_at(-3,3,0,6,2,2.2);box_at(-3,20,0,6,.8,.7);}
}
if(part=="front") front_native();
else if(part=="carrier") translate([0,0,-carrier_z]) carrier_native();
else if(part=="rear") translate([0,0,case_depth]) rotate([180,0,0]) rear_native();
else if(part=="stand") stand_native();
else if(part=="coupon_pins") coupon_pins();
else if(part=="coupon_holes") coupon_holes();
else if(part=="coupon_latch") coupon_latch();
else if(part=="coupon_socket") coupon_socket();
else if(part=="release_key") release_key();
else if(part=="exploded") assembly(25);
else if(part=="section") intersection(){assembly();box_at(-100,-150,-1,100,240,250);}
else if(part=="hardware") standing() hardware_native();
else if(part=="ribbon") standing() ribbons_native();
else if(part=="wires") standing() wires_native();
else if(part=="power_external") power_external();
else if(part=="assembly") assembly();
else if(part=="none") {}
else assert(false,str("Unknown part: ",part));
