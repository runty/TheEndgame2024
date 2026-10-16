use <vendor/Choc_Chicago_Steno_Thumb.scad>
use <vendor/Choc_Chicago_Steno_Convex.scad>
profile="sculpted";
long=true;
mirrored=false;
module cap() {
  if(profile=="sculpted") {
    rotate([0,0,long ? 90 : 0])
      keycap_cs_thumb(keyID=long ? 3 : 2, Stem=1, StemRot=long ? 90 : 0, fdm=false);
  } else {
    keycap_cs_convex(keyID=long ? 3 : 1, Stem=1, StemRot=0);
  }
}
if(mirrored) mirror([1,0,0]) cap(); else cap();
