import logging

from django.http import HttpResponse
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.views.static import serve

from .models import Case, DICOMInstance

logger = logging.getLogger(__name__)
# from django.contrib.staticfiles import views as static_views


@login_required
def serve_media(request, path):
    """Serve a file that should only be available to logged-in users."""
    if "localhost" in request.headers["Host"] or "127.0.0.1" in request.headers["Host"]:
        if settings.DEBUG:
            # We're not running behind nginx so we are going to just serve the file ourselves.
            return serve(request, path, settings.MEDIA_ROOT)
        else:
            return HttpResponse(status_code=500)

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
                login(request, user)
                return redirect("/")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    form = AuthenticationForm()
    return render(request, "login.html", context={"form": form})


def logout_request(request):
    logout(request)
    return redirect("/login")


# TODO: Status viewer from django rq - Case Information button is clicked


@login_required
def index(request):
    data = []
    objects = Case.objects.all()
    for object in objects:
        data.append(
            {
                'case_id': str(object.id),
                "patient_name": object.patient_name,
                "mrn": object.mrn,
                "acc": object.acc,
                "num_spokes": object.num_spokes,
                "case_type": object.case_type,
                "exam_time": object.exam_time.strftime("%Y-%m-%d %H:%M"),
                "receive_time": object.receive_time.strftime("%Y-%m-%d %H:%M"),
                "status": Case.CaseStatus(object.status).name.title(),
                "twix_id": object.twix_id,
                "case_location": object.case_location,
                "settings": object.settings,
                "last_read_by_id": object.last_read_by.username if object.last_read_by_id else "",
                "viewed_by_id": object.viewed_by.username if object.viewed_by_id else "",
            }
        )

    context = {"data": data}
    return render(request, "index.html", context)


@login_required
def user(request):
    context = {}
    return render(request, "user.html", context)


@login_required
def config(request):
    context = {}
    return render(request, "config.html", context)


@login_required
def viewer(request, case):
    case = Case.objects.get(id=case)
    dicom_set = case.dicom_sets.get(type="Incoming")
    instances = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set__type=("ORI")).order_by("study_uid","dicom_set").distinct("study_uid","dicom_set")

    context = {
        # "series": set([(k.study_uid, k.series_uid) for k in instances]),
        "studies": [(k.study_uid,k.dicom_set.id, k.dicom_set.type) for k in instances],
        "case": instances[0].dicom_set.case,
    }
    return render(request, "viewer.html", context)


@login_required
def remove(request, case_id):
    print("CASE to delete: ", case_id)
    case = Case.objects.get(id=case_id)
    case.status = Case.CaseStatus.DELETE
    case.save()
    return HttpResponse(f"<html><body><span>Remove {case_id}</span></body></html>")