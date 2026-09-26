#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v openscad >/dev/null || { echo 'OpenSCAD is required.' >&2; exit 1; }
mkdir -p stl checks
for p in front carrier rear stand coupon_pins coupon_holes coupon_latch coupon_socket release_key; do
  openscad -o "stl/${p}.stl" -D "part=\"$p\"" counterframe.scad 2>"checks/${p}_openscad.log"
done
