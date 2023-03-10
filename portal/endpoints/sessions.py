import json

from django.http import HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

from portal.models import *
from .common import user_opened_case

@login_required
def handle_session(request, case, session_id=None):
    if request.method == "POST":
        if not user_opened_case(request, case):
            return HttpResponseForbidden()
        return update_session(request, case, session_id)
    elif request.method == "GET":
        return get_session(request, case, session_id)
    else:
        return HttpResponseNotAllowed(["POST","GET"])


@login_required
def new_session(request,case):
    if not user_opened_case(request, case):
        return HttpResponseForbidden()
    session = SessionInfo(case=Case.objects.get(id=case), cameras=[], voi={}, annotations=[], user=request.user)
    session.save()
    return JsonResponse(session.to_dict())


@login_required
@require_GET
def all_sessions(request,case):
    sessions = SessionInfo.objects.filter(case=Case.objects.get(id=case), user=request.user)
    return JsonResponse(dict(sessions=[dict(id=s.id, created_at=s.created_at.timestamp(), updated_at=s.updated_at.timestamp()) for s in sessions]))


def update_session(request,case,session_id=None):
    new_state = json.loads(request.body)
    if not session_id:
        try:
            session = SessionInfo.objects.get(case=Case.objects.get(id=case), user=request.user)
        except SessionInfo.DoesNotExist:
            session = SessionInfo(case=Case.objects.get(id=case), user=request.user)
    else:
        session = get_object_or_404(SessionInfo,case=Case.objects.get(id=case), user=request.user, id=session_id)

    session.cameras = new_state.get("cameras",[])
    session.annotations = new_state.get("annotations",[])
    session.voi = new_state.get("voi",{})
    session.updated_at = timezone.now()
    session.save()
    return JsonResponse(dict(error="", action="", ok=True))


def get_session(request, case, session_id=None):
    if session_id:
        session = get_object_or_404(SessionInfo,  id=session_id,case=case, user=request.user)
    else:
        try:
            session = SessionInfo.objects.filter(case=case, user=request.user).latest("updated_at")
        except SessionInfo.DoesNotExist:
            return new_session(request,case)
    return JsonResponse(session.to_dict())
