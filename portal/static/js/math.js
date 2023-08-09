const ident = () => [
    [1,0,0],
    [0,1,0],
    [0,0,1]
]
const empty = () => [
    [0,0,0],
    [0,0,0],
    [0,0,0]
]
const rot_x = (angle) => [
    [1, 0, 0],
    [0, Math.cos(angle), -Math.sin(angle)],
    [0, Math.sin(angle), Math.cos(angle)]
  ];
const rot_y = (angle) => [
    [Math.cos(angle), 0, Math.sin(angle)],
    [0, 1, 0],
    [-Math.sin(angle), 0, Math.cos(angle)]
];

const rot_z = (angle) => [
    [Math.cos(angle), -Math.sin(angle), 0],
    [Math.sin(angle), Math.cos(angle), 0],
    [0, 0, 1]
];
function mul(a,b) {
  const out = ident()
  vtk.Common.Core.vtkMath.multiply3x3_mat3(flatten_array(a),flatten_array(b),out);
  return unflatten_array(out);
}
function generate_array(x,y,z) {
  const out = ident()
  vtk.Common.Core.vtkMath.multiply3x3_mat3(rot_x(x),rot_y(y),out)
  const out_2 = ident()
  vtk.Common.Core.vtkMath.multiply3x3_mat3(out,rot_z(z),out_2)
  return out_2
}
function mod(n, m) {
  return ((n % m) + m) % m;
}
function random_array() {
  angles = [0,0,0].map(x=>Math.random() * 2*Math.PI);
  return generate_array(...angles);
}
function snap_array_a(arr_in) {
  let arr = new Array(arr_in.length);
  for (var k=0; k<arr_in.length; ++k)
    arr[k] = arr_in[k].slice();

  for (var i=0; i < arr.length; i++) {
    let max = 0;
    let max_idx = 0;
    for ( var j=0; j<arr[i].length; j++) {
      if (Math.abs(arr[i][j]) > Math.abs(max)) {
        max = arr[i][j];
        max_idx = j;
      }
    }
    arr[i][0] = 0;
    arr[i][1] = 0;
    arr[i][2] = 0;
    arr[i][max_idx] = Math.sign(max);
    arr[(i+1)%3][max_idx] = 0;
    arr[(i+2)%3][max_idx] = 0;
    // console.table(arr)
  }
  return arr;
}
function snap_array_b(arr_in) {
  let arr = new Array(arr_in.length);
  for (var k=0; k<arr_in.length; ++k)
    arr[k] = arr_in[k].slice();

  for (var i=0; i < 3; i++) {
    let max = 0;
    let max_idx = -1;
    for ( var j=0; j<3; j++) {
      // console.log(j,i, arr[j][i], max, max_idx)
      if (Math.abs(arr[j][i]) > Math.abs(max)) {
        max = arr[j][i];
        max_idx = j;
      }
    }
    arr[0][i] = 0;
    arr[1][i] = 0;
    arr[2][i] = 0;
    arr[max_idx][i] = Math.sign(max);
    arr[max_idx][(i+1)%3] = 0;
    arr[max_idx][(i+2)%3] = 0;
  }
  return arr;
}
function rotationMatrixToEulerAngles(R) {
  var sy = Math.sqrt(R[0][0] * R[0][0] + R[1][0] * R[1][0]);

  var singular = sy < 1e-6;

  if (!singular) {
      var x = Math.atan2(R[2][1], R[2][2]);
      var y = Math.atan2(-R[2][0], sy);
      var z = Math.atan2(R[1][0], R[0][0]);
  } else {
      var x = Math.atan2(-R[1][2], R[1][1]);
      var y = Math.atan2(-R[2][0], sy);
      var z = 0;
  }
  return [ x, y, z ]
}
function roundPi(x) {
  return Math.round( 2 * x / Math.PI ) / 2 * Math.PI
}
function arr_eq(arr1, arr2) {
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      if (arr1[i][j] !== arr2[i][j]) {
        return false;
      }
    }
  }
  return true;
}
function test_angles(x,y,z) {
  const arr = mul(mul(rot_z(z),rot_y(y)),rot_x(x))
  console.table(arr);
  const a = snap_array_b(arr)
  const b = snap_array_c(arr)
  if (!arr_eq(a,b)){
    console.table(a)
    console.table(b)
    return false
  }
  return true;
}
function do_test() {
  for (let i=-Math.PI/5;i<Math.PI/5.; i+= Math.PI/17) {
    for (let j=-Math.PI/5;j<Math.PI/5.; j+= Math.PI/17) {
      for (let k=-Math.PI/5;k<Math.PI/5.; k+= Math.PI/17) {
        if (!test_angles(i,j,k)) {
            console.log(i,j,k);
            return false;
          }
      }
    }
  }
  return true;
}

function snap_rotation_matrix(arr) {
    let angles = rotationMatrixToEulerAngles(arr).map(roundPi);
    let out = mul(mul(rot_z(angles[2]),rot_y(angles[1])),rot_x(angles[0]))
    return out.map(x=>x.map(y=>Math.round(y)))
}

function snap_image_direction(imageData){ 
    const arr = unflatten_array(imageData.getDirection());
    let result = snap_rotation_matrix(arr);
    imageData.setDirection(flatten_array(result));
}
function flatten_array(arr) {
  return [...arr[0].slice(),...arr[1].slice(),...arr[2].slice()];
}
function unflatten_array(arr) {
    return [arr.slice(0,3), arr.slice(3,6),arr.slice(6,9)]
}

export { snap_image_direction };