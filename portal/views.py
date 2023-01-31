import logging
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.views.static import serve
# from django.contrib.staticfiles import views as static_views

from .models import Case, DICOMInstance

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


# TODO: Status viewer from django rq - Case Information button is clicked

def extract_case(object):

    return { 
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

@login_required
def index(request):
    data = []
    objects = Case.objects.all()
    for object in objects:
        data.append(extract_case(object))

    context = {
        "data": data,
        "cases": Case.objects.filter(status = Case.CaseStatus.VIEWING)
    }
    return render(request, "index.html", context)


@login_required
def user(request):
    context = {
        "cases": Case.objects.filter(status = Case.CaseStatus.VIEWING)
    }
    return render(request, "user.html", context)


@login_required
def config(request):
    context = {
        "cases": Case.objects.filter(status = Case.CaseStatus.VIEWING)
    }
    return render(request, "config.html", context)


@login_required
def viewer(request, case):
    case = get_object_or_404(Case, id=case)
    
    case.viewed_by = request.user
    case.last_read_by = request.user
    case.status = Case.CaseStatus.VIEWING
    case.save()
    instances = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set__type__in=("ORI", "SUB")).order_by("study_uid","dicom_set").distinct("study_uid","dicom_set")
    
    context = {
        "studies": [(k.study_uid,k.dicom_set.id, k.dicom_set.type) for k in instances],
        "current_case": extract_case(instances[0].dicom_set.case),
        "cases": Case.objects.filter(status = Case.CaseStatus.VIEWING)
    }
    return render(request, "viewer.html", context)

    
@login_required
def add_case(request):
    # TODO: Enable viewing and deleting only when "Ready" 
    cases = Case.objects.filter(viewed_by=request.user)
    context = {
        "cases": [(k.id) for k in cases],
    }
    return render(request, "portal.html", context)


@login_required
def browser_get_all_cases(request):
    '''
    Returns a JSON object containing information on all cases stored in the database.
    '''
    case_data = []
    all_cases = Case.objects.all()
    for case in all_cases:
        case_data.append(
            {
                "case_id": str(case.id),
                "patient_name": case.patient_name,
                "mrn": case.mrn,
                "acc": case.acc,
                "num_spokes": case.num_spokes,
                "case_type": case.case_type,
                "exam_time": case.exam_time.strftime("%Y-%m-%d %H:%M"),
                "receive_time": case.receive_time.strftime("%Y-%m-%d %H:%M"),
                "status": Case.CaseStatus(case.status).name.title(),
                "twix_id": case.twix_id,
                "case_location": case.case_location,
                "settings": case.settings,
                "last_read_by_id": case.last_read_by.username if case.last_read_by_id else "",
                "viewed_by_id": case.viewed_by.username if case.viewed_by_id else "",
            }
        )

    return JsonResponse({"data": case_data}, safe=False)


@login_required
def browser_get_case(request, case):
    '''
    Returns information about the given case in JSON format. Returns 404 page if
    case ID does not exist
    '''
    case = get_object_or_404(Case, id=case)

    json_data = {
        "case_id": str(case.id),
        "patient_name": case.patient_name,
        "mrn": case.mrn,
        "acc": case.acc,
        "num_spokes": case.num_spokes,
        "case_type": case.case_type,
        "exam_time": case.exam_time.strftime("%Y-%m-%d %H:%M"),
        "receive_time": case.receive_time.strftime("%Y-%m-%d %H:%M"),
        "status": Case.CaseStatus(case.status).name.title(),
        "twix_id": case.twix_id,
        "case_location": case.case_location,
        "settings": case.settings,
        "last_read_by_id": case.last_read_by.username if case.last_read_by_id else "",
        "viewed_by_id": case.viewed_by.username if case.viewed_by_id else "",
    }
    return JsonResponse(json_data, safe=False)

