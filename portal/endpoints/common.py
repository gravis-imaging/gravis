from portal.models import Case
import numpy as np, math
from django.core.exceptions import BadRequest
import json

def json_load_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except:
        raise BadRequest()

cross = (lambda x,y:np.cross(x,y)) # fix type inference bug

def user_opened_case(request, case):
    if not type(case) is Case:
        case = Case.objects.get(id=case)
    return case.status == Case.CaseStatus.VIEWING and case.viewed_by == request.user

def rot_x(angle):
    return np.asarray([
        [1, 0, 0],
        [0, math.cos(angle), -math.sin(angle)],
        [0, math.sin(angle), math.cos(angle)]
    ])

def rot_y(angle):
    return np.asarray([
    [math.cos(angle), 0, math.sin(angle)],
    [0, 1, 0],
    [-math.sin(angle), 0, math.cos(angle)]]);

def rot_z(angle):
    return np.asarray([
    [math.cos(angle), -math.sin(angle), 0],
    [math.sin(angle), math.cos(angle), 0],
    [0, 0, 1]
])

def rotationMatrixToEulerAngles(R):
    sy = math.sqrt(R[0,0] * R[0,0] +  R[1,0] * R[1,0])
    singular = sy < 1e-6
    if not singular:
        x = math.atan2(R[2,1] , R[2,2])
        y = math.atan2(-R[2,0], sy)
        z = math.atan2(R[1,0], R[0,0])
    else:
        x = math.atan2(-R[1,2], R[1,1])
        y = math.atan2(-R[2,0], sy)
        z = 0
    return [x, y, z]

def roundPi(x):
  return round( 2 * x / math.pi ) / 2 * math.pi

def snap_rotation_matrix(arr):
    angles = list(map(roundPi,rotationMatrixToEulerAngles(arr)))
    out = (rot_z(angles[2]) @ rot_y(angles[1])) @ rot_x(angles[0])
    return np.rint(out)


def get_im_orientation_mat(metadata):
    im_orientation_patient = np.asarray(metadata["00200037"]["Value"]).reshape((2,3))
    orient_mat = (np.vstack((im_orientation_patient,[cross(*im_orientation_patient)])))
    return snap_rotation_matrix(orient_mat)