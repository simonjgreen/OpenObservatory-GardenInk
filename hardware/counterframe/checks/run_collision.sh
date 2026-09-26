#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
for t in front_carrier front_rear carrier_rear stand_case hardware_carrier hardware_rear ribbon_carrier ribbon_rear ribbon_front wires_rear wires_carrier usb_stand; do
 rm -f "$t.stl"
 openscad -D 'part="none"' -o "$t.stl" "$t.scad" 2>"$t.log" || true
done
