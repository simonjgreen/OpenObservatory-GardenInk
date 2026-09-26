include <../counterframe.scad>
intersection(){ stand_native(); standing() union(){front_native();carrier_native();rear_native();}; }
