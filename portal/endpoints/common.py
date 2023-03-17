from portal.models import Case
import numpy as np
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

def get_im_orientation_mat(metadata):
    im_orientation_patient = np.asarray(metadata["00200037"]["Value"]).reshape((2,3))
    return np.rint(np.vstack((im_orientation_patient,[cross(*im_orientation_patient)])))