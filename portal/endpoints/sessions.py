import json

from django.http import HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

from portal.models import *
from .common import json_load_body, user_opened_case, debug_sql
from django.db import transaction
from django.views.decorators.http import require_http_methods

@login_required
@transaction.atomic
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
@transaction.atomic
def new_session(request,case):
    # if not user_opened_case(request, case):
    #     return HttpResponseForbidden()
    session = SessionInfo(case_id=int(case), cameras=[], voi={}, annotations=[], user=request.user)
    session.save()
    return JsonResponse(session.to_dict())


@login_required
@require_GET
def all_sessions(request,case):
    sessions = SessionInfo.objects.filter(case_id=int(case), user=request.user)
    return JsonResponse(dict(sessions=[dict(id=s.id, created_at=s.created_at.timestamp(), updated_at=s.updated_at.timestamp()) for s in sessions]))


def update_session(request,case,session_id=None):
    new_state = json_load_body(request)
    if not session_id:
        try:
            session = SessionInfo.objects.get(case_id=int(case), user=request.user)
        except SessionInfo.DoesNotExist:
            session = SessionInfo(case_id=int(case), user=request.user)
    else:
        session = get_object_or_404(SessionInfo, case_id=int(case), user=request.user, id=session_id)

    session.cameras = new_state.get("cameras",[])
    session.voi = new_state.get("voi",{})
    session.updated_at = timezone.now()

    if session.annotation_group_id:
        session.annotation_group.annotations = new_state.get("annotations", [])
        session.annotation_group.updated_at = timezone.now()
        session.annotation_group.save()
        # annotations field on session is not used when a group is linked
    else:
        session.annotations = new_state.get("annotations",[])

    session.save()
    return JsonResponse(dict(error="", action="", ok=True))


def get_session(request, case, session_id=None):
    if session_id:
        session = get_object_or_404(SessionInfo, id=session_id, case=case, user=request.user)
    else:
        try:
            session = SessionInfo.objects.filter(case_id=int(case), user=request.user).latest("updated_at")
        except SessionInfo.DoesNotExist:
            return new_session(request,case)
    return JsonResponse(session.to_dict())


def _get_or_create_session(user, case_id):
    """Return the user's most recent session for case_id, creating one if needed."""
    try:
        return SessionInfo.objects.filter(case_id=case_id, user=user).latest("updated_at")
    except SessionInfo.DoesNotExist:
        session = SessionInfo(case_id=case_id, cameras=[], voi={}, annotations=[], user=user)
        session.save()
        return session


@login_required
@require_POST
@transaction.atomic
def create_annotation_group(request, case):
    """Create a new AnnotationGroup from the current session's annotations and link it."""
    session = _get_or_create_session(request.user, int(case))
    group = AnnotationGroup.objects.create(
        user=request.user,
        annotations=session.annotations,
    )
    group.cases.add(session.case)
    session.annotation_group = group
    session.annotations = []
    session.updated_at = timezone.now()
    session.save()
    return JsonResponse(group.to_dict())


@login_required
@require_POST
@transaction.atomic
def join_annotation_group(request, case, group_id):
    """Link the current case's session to an existing AnnotationGroup."""
    group = get_object_or_404(AnnotationGroup, id=group_id, user=request.user)
    session = _get_or_create_session(request.user, int(case))
    session.annotation_group = group
    session.annotations = []
    session.updated_at = timezone.now()
    session.save()
    group.cases.add(session.case)
    return JsonResponse(session.to_dict())


@login_required
@require_POST
@transaction.atomic
def leave_annotation_group(request, case):
    """Detach the current session from its AnnotationGroup, keeping a local snapshot."""
    session = _get_or_create_session(request.user, int(case))
    if session.annotation_group:
        group = session.annotation_group
        session.annotations = list(group.annotations)
        group.cases.remove(session.case)
        session.annotation_group = None
        session.updated_at = timezone.now()
        session.save()
        if group.cases.count() == 0:
            group.delete()
    return JsonResponse(session.to_dict())


@login_required
@require_GET
def list_annotation_groups(request):
    """Return all AnnotationGroups owned by the current user."""
    groups = AnnotationGroup.objects.filter(user=request.user).prefetch_related('cases', 'cases__shadow')
    privacy_mode = request.user.profile.privacy_mode
    return JsonResponse(dict(annotation_groups=[g.to_dict(privacy_mode) for g in groups]))
