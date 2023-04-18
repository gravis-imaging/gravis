import logging
import json
import shutil
from django.http import HttpResponse, HttpResponseBadRequest,HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.views.static import serve
from django.contrib.auth.models import User
from django.db import transaction
from django import forms

from portal.endpoints.filebrowser import SubmitForm

# from django.contrib.staticfiles import views as static_views

from .models import Case, DICOMInstance, Tag, UserProfile
from .forms import UserForm, ProfileForm, ProfileUpdateForm


logger = logging.getLogger(__name__)


@login_required
def serve_media(request, path):
    """Serve a file that should only be available to logged-in users."""
    if "localhost" in request.headers["Host"] or "127.0.0.1" in request.headers["Host"]:
        if settings.DEBUG:
            # We're not running behind nginx so we are going to just serve the file ourselves.
            return serve(request, path, settings.MEDIA_ROOT)
        else:
            return HttpResponse(status=500)

    # Use nginx's implementation of "x-sendfile" to tell nginx to serve the actual file.
    # see: https://www.nginx.com/resources/wiki/start/topics/examples/x-accel/
    return HttpResponse(
        headers={"X-Accel-Redirect": "/secret/" + path, "Content-Type": ""}
    )


def login_request(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                try:
                    UserProfile.objects.get(user=user.id)
                except UserProfile.DoesNotExist:                
                    UserProfile.objects.create(user=user)
                login(request, user)
                return redirect("/")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")

    form = AuthenticationForm()
    return render(request, "login.html", context={"form": form, "build_version": settings.GRAVIS_VERSION})


def logout_request(request):
    logout(request)
    return redirect("/login")


def calc_disk_usage():
    total, used, free = shutil.disk_usage(settings.CASES_FOLDER)
    percent = 100*used/float(total)

    if free < 10e9:
        warn = "bg-danger"
    elif free < 30e9:
        warn = "bg-warning"
    else:
        warn = ""
    return dict(total=total,used=used,free=free,percent = percent, warn=warn)


@login_required
def index(request):
    context = {"disk_usage":calc_disk_usage()}
    return render(request, "index.html", context)


@login_required
def user(request):
    current_user = get_object_or_404(User,username=request.user)
    show_confirm = False

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            try:           
                current_user.profile.privacy_mode = bool(form.cleaned_data.get("privacy_mode"))
                current_user.profile.save() 
                show_confirm = True
            except Exception as e:
                logger.exception("Error while saving profile data")
                return HttpResponseBadRequest('Unable to save data')   
        else:
            return HttpResponseBadRequest('Invalid form data')   
        
    user_form = UserForm(instance=request.user)
    profile_form = ProfileForm(instance=request.user.profile)

    return render(request, "user.html", {
        'user_form': user_form, 
        'profile_form': profile_form,
        'show_confirm': show_confirm,
    })


@login_required
def config(request):
    tags = [(tag.name, tag.case_set.all().count(), [case.to_dict(request.user.profile.privacy_mode) for case in tag.case_set.all()]) for tag in Tag.objects.all()]
    
    # sort tags by number of occurrences in cases
    tags.sort(key=lambda a: a[1])
    context = {
        "tags": tags,
        "disk_usage":calc_disk_usage()
    }
    return render(request, "config.html", context)


@login_required
def viewer(request, case_id):
    read_only = False
    with transaction.atomic():
        case = get_object_or_404(Case, id=case_id)
        # TODO: Check if current user is allowed to view case
        
        # If the case is not ready for viewing
        if case.status not in ( Case.CaseStatus.READY, Case.CaseStatus.VIEWING,  Case.CaseStatus.COMPLETE):
            return HttpResponseForbidden()

        # If the case is currently being viewed, but not by this user
        if ( case.status == Case.CaseStatus.VIEWING and case.viewed_by != request.user ):
            read_only = True
        else:
            case.viewed_by = request.user
            case.last_read_by = request.user
            case.status = Case.CaseStatus.VIEWING
            case.save()

    instances = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set__type__in=("ORI", "SUB")).order_by("study_uid","dicom_set").distinct("study_uid","dicom_set")
    
    context = {
        "studies": [dict(uid=k.study_uid,dicom_set=k.dicom_set.id, type=k.dicom_set.type) for k in instances],
        "current_case": case.to_dict(request.user.profile.privacy_mode),
        "original_dicom_set_id": instances[0].dicom_set.id,
        "read_only": "true" if read_only else "false"
    }
    return render(request, "viewer.html", context)


@login_required
def file_browser(request):
    form = SubmitForm()
    context = {"form": form,
               "disk_usage":calc_disk_usage()}
    return render(request, "filebrowser.html", context)

@login_required
def case_details(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    jobs = case.processing_jobs.order_by("id").all()
    context = {"case": case, "jobs":jobs}
    return render(request, "case_info.html", context)