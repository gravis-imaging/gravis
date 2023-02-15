import logging
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.views.static import serve
# from django.contrib.staticfiles import views as static_views

from .models import Case, DICOMInstance, Tag

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

@login_required
def index(request):
    context = {
        "viewer_cases": Case.objects.filter(status = Case.CaseStatus.VIEWING, viewed_by=request.user)
    }
    return render(request, "index.html", context)


@login_required
def user(request):
    context = {
        "viewer_cases": Case.objects.filter(status = Case.CaseStatus.VIEWING, viewed_by=request.user)
    }
    return render(request, "user.html", context)


@login_required
def config(request):
    context = {
        "viewer_cases": Case.objects.filter(status = Case.CaseStatus.VIEWING, viewed_by=request.user),
        "tags": [(tag.name, tag.case_set.all().count()) for tag in Tag.objects.all()]
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
        "viewer_cases": Case.objects.filter(status = Case.CaseStatus.VIEWING, viewed_by=request.user),
        "original_dicom_set_id": instances[0].dicom_set.id,
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


def extract_case(case_object):

    return { 
        'case_id': str(case_object.id),
        "patient_name": case_object.patient_name,
        "mrn": case_object.mrn,
        "acc": case_object.acc,
        "num_spokes": case_object.num_spokes,
        "case_type": case_object.case_type,
        "exam_time": case_object.exam_time.strftime("%Y-%m-%d %H:%M"),
        "receive_time": case_object.receive_time.strftime("%Y-%m-%d %H:%M"),
        "status": Case.CaseStatus(case_object.status).name.title(),
        "twix_id": case_object.twix_id,
        "case_location": case_object.case_location,
        "settings": case_object.settings,
        "last_read_by_id": case_object.last_read_by.username if case_object.last_read_by_id else "",
        "viewed_by_id": case_object.viewed_by.username if case_object.viewed_by_id else "",
        "tags": [tag.name for tag in case_object.tags.all()]
    }


@login_required
def browser_get_cases_all(request):
    '''
    Returns a JSON object containing information on all cases stored in the database.
    '''
    case_data = []
    all_cases = Case.objects.all()
    for case in all_cases:
        case_data.append(extract_case(case))

    return JsonResponse({"data": case_data}, safe=False)


@login_required
def browser_get_tags_all(request):
    '''
    Returns a JSON object containing information on all tags stored in the database.
    '''
    # tags = [tag.name for tag in Tag.objects.all()]
    # all_tags = Tag.objects.all()
    # for tag in all_tags:
    #     tags.append(tag.name)
    return JsonResponse({"tags": [(tag.name, tag.case_set.all().count()) for tag in Tag.objects.all()]}, safe=False)


@login_required
def browser_get_case_tags_and_all_tags(request, case_id):
    '''
    Returns a JSON object containing information on all tags stored in the database 
    and tags specific to the current case.
    '''
    # tags = []
    # all_tags = Tag.objects.all()
    # for tag in all_tags:
    #     tags.append(tag.name)

    case = get_object_or_404(Case, id=case_id)

    return JsonResponse({"tags": [tag.name for tag in Tag.objects.all()], "case_tags": [tag.name for tag in case.tags.all()]}, safe=False)


@login_required
def browser_get_case(request, case):
    '''
    Returns information about the given case in JSON format. Returns 404 page if
    case ID does not exist
    '''
    case = get_object_or_404(Case, id=case)

    json_data = extract_case(case)
    return JsonResponse(json_data, safe=False)


@login_required
def update_case_tags(request):
    if request.method == 'POST':        
        import json
        body = json.loads(request.body.decode('utf-8'))
        case_id = body['case_id']
        case = get_object_or_404(Case, id=case_id)
        tags = body['tags']

        # clear old tags from the case, but keep the tags in db
        old_tags = case.tags.all()
        for old_tag in old_tags:
            case.tags.remove(old_tag)

        for tag in tags:
            existing_tag = Tag.objects.filter(name=tag).first()
            if(existing_tag is None):
                new_tag = Tag(name=tag)
                new_tag.save()
                case.tags.add(new_tag)
                # new_tag.cases.add(case)                
            else:
                case.tags.add(existing_tag)
                # existing_tag.cases.add(case)               
            
        return HttpResponse('OK') 
    # nothing went well
    return HttpResponseBadRequest("Only POST method is implemented.")


 
@login_required
def update_tags(request):
    if request.method == 'POST':        
        import json
        body = json.loads(request.body.decode('utf-8'))
        tags = body['tags']
        for tag_name in tags:
            tag = get_object_or_404(Tag, name=tag_name)
            tag.delete()          
            
        return HttpResponse('OK') 
    # nothing went well
    return HttpResponseBadRequest("Only POST method is implemented.")

    
   

