use <so3.scad>

function val(a=undef,default=undef) = a == undef ? default : a;
function vec_is_undef(x,index_=0) = index_ >= len(x) ? true :
is_undef(x[index_]) && vec_is_undef(x,index_+1);

// The changes below fix the openscad warnings on newer versions.
// The changes are based on the authors instructions on how to fix the
// warnings on discord:
// https://discord.com/channels/669011382284451861/831948386198093834/944018319575515157
//function is_undef(x) = len(x) > 0 ? vec_is_undef(x) : x == undef;

// Either a or b, but not both
function either(a,b,default=undef) = is_undef(a) ? (is_undef(b) ? default : -b) : is_undef(b) ? a : undef;

function translationv(left=undef,right=undef,up=undef,down=undef,forward=undef,backward=undef,translation=undef) =
translationv_2(
    x = either(up,down),
    y = either(right,left),
    z = either(forward,backward),
    translation = translation);

function translationv_2(x,y,z,translation) =
	x == undef && y == undef && z == undef ? translation :
	is_undef(translation) ? [val(x,0),val(y,0),val(z,0)]
	: undef;

function rotationv(pitch=undef,yaw=undef,roll=undef,rotation=undef) =
	rotation == undef ? [val(yaw,0),val(pitch,0),val(roll,0)] :
	pitch == undef && yaw == undef && roll == undef ? rotation :
	undef;

function trajectory(
	left=undef,    right=undef,
	up=undef,      down=undef,
	forward=undef, backward=undef,
	translation=undef,

    pitch=undef,
    yaw=undef,
    roll=undef,
    rotation=undef
) = concat(
	translationv(left=left,right=right,up=up,down=down,forward=forward,backward=backward,translation=translation),
	rotationv(pitch=pitch,yaw=yaw,roll=roll,rotation=rotation)
);

function rotationm(rotation=undef,pitch=undef,yaw=undef,roll=undef) = so3_exp(rotationv(rotation=rotation,pitch=pitch,yaw=yaw,roll=roll));
