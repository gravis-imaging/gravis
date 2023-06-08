from portal.models import Case
import numpy as np, math
from django.core.exceptions import BadRequest
import json
import functools
import logging

def debug_sql(func):
    @functools.wraps(func)
    def wrapper(*args,**kwargs):
        l = logging.getLogger('django.db.backends')
        level = l.level
        l.setLevel(logging.DEBUG)
        try:
            return func(*args,**kwargs)
        finally:
            l.setLevel(level)
    return wrapper

def json_load_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except:
        raise BadRequest()

def user_opened_case(request, case):
    if not type(case) is Case:
        case = Case.objects.only("status","viewed_by_id").get(id=case)
    return case.status == Case.CaseStatus.VIEWING and case.viewed_by_id == request.user.id
