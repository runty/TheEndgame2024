// Six caps: four 1.5u and two 1u, in two rows of three.
// GPL-3.0; see README.md for provenance, scale, and cutting instructions.
profile="sculpted";
module cap(is_long, right_hand) {
    name = profile=="sculpted"
      ? str("../single-caps/sculpted-",is_long ? "long" : "small", "-",right_hand ? "right" : "left",".stl")
      : str("../single-caps/convex-",is_long ? "long" : "small",".stl");
    import(name, convexity=10);
}
// All shells share skirt Z=0. Raise the finished assembly to a nonnegative Z.
translate([46,23,1.3]) union() {
    // Permanent carrier spine: 3 x 3 mm. Twelve cut gates: 1.8 x 1.8 mm.
    translate([-38,-1.5,0]) cube([76,3,3]);
    for(row=[-1,1]) for(col=[0:2]) {
        x=(col-1)*32;
        translate([x,row*14,0]) cap(col<2,row<0);
        for(dx=[-4,4])
            translate([x+dx-.9, row>0 ? 0 : -7.2, .1]) cube([1.8,7.2,1.8]);
    }
}
