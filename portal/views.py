import logging
import json
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.views.static import serve
from django.contrib.auth.models import User
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


@login_required
def index(request):
    context = {}
    return render(request, "index.html", context)


@login_required
def user(request):
    current_user = get_object_or_404(User,username=request.user)
    show_confirm = False

    if request.method == 'POST':
        print(request.POST)
        form = ProfileUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            try:           
                current_user.profile.privacy_mode = bool(form.cleaned_data.get("privacy_mode"))
                current_user.profile.save() 
                show_confirm = True
            except Exception as e:
                print("Error while saving profile data")
                print(e)
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
    tags = [(tag.name, tag.case_set.all().count(), [{'id': case.id, 'patient_name': case.patient_name, 'mrn': case.mrn, 'acc': case.acc} 
            for case in tag.case_set.all()]) for tag in Tag.objects.all()]
    # sort tags by number of occurrences in cases
    tags.sort(key=lambda a: a[1])
    context = {
        "tags": tags,
    }
    return render(request, "config.html", context)


@login_required
def viewer(request, case_id):
    case = get_object_or_404(Case, id=case_id)
    # TODO: Check if current user is allowed to view case
    
    case.viewed_by = request.user
    case.last_read_by = request.user
    case.status = Case.CaseStatus.VIEWING
    case.save()

    instances = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set__type__in=("ORI", "SUB")).order_by("study_uid","dicom_set").distinct("study_uid","dicom_set")
    
    context = {
        "studies": [dict(uid=k.study_uid,dicom_set=k.dicom_set.id, type=k.dicom_set.type) for k in instances],
        "current_case": case.to_dict(request.user.profile.privacy_mode),
        "original_dicom_set_id": instances[0].dicom_set.id,
    }
    return render(request, "viewer.html", context)


@login_required
@require_POST
def case_status(request, case_id, new_status):
    case = get_object_or_404(Case, id=case_id)

    if case.status != Case.CaseStatus.VIEWING:
        return HttpResponseBadRequest

    case.viewed_by = None;

    if new_status=="ready":
        case.status = Case.CaseStatus.READY
        case.save()
    elif new_status=="complete":
        case.status = Case.CaseStatus.COMPLETE
        case.save()
    else:
        return HttpResponseBadRequest

    return HttpResponse() 

@login_required
def browser_get_cases_all(request):
    '''
    Returns a JSON object containing information on all cases stored in the database.
    '''
    case_data = [case.to_dict(request.user.profile.privacy_mode) for case in Case.objects.all()]
    return JsonResponse({"data": case_data}, safe=False)


@login_required
def browser_get_tags_all(request):
    '''
    Returns a JSON object containing information on all tags stored in the database.
    '''
    return JsonResponse({"tags": [(tag.name, tag.case_set.all().count()) for tag in Tag.objects.all()]}, safe=False)


@login_required
def browser_get_case_tags_and_all_tags(request, case_id):
    '''
    Returns a JSON object containing information on all tags stored in the database 
    and tags specific to the current case.
    '''
    case = get_object_or_404(Case, id=case_id)
    return JsonResponse({"tags": [tag.name for tag in Tag.objects.all()], "case_tags": [tag.name for tag in case.tags.all()]}, safe=False)


@login_required
def browser_get_case(request, case_id):
    '''
    Returns information about the given case in JSON format. Returns 404 page if
    case ID does not exist
    '''
    case = get_object_or_404(Case, id=case_id)
    json_data = case.to_dict(request.user.profile.privacy_mode)
    return JsonResponse(json_data, safe=False)


@login_required
@require_POST
def update_case_tags(request):
    '''
    Updates tags for a given case and returns response.ok if successful
    '''
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
        
    return HttpResponse() 

 
@login_required
@require_POST
def update_tags(request):
    '''
    Delete selected tags and returns response.ok if successful
    '''
    body = json.loads(request.body.decode('utf-8'))
    tags = body['tags']
    for tag_name in tags:
        tag = get_object_or_404(Tag, name=tag_name)
        tag.delete()                  

    return HttpResponse() 


@login_required
@require_POST
def browser_delete_case(request, case_id):
    case=get_object_or_404(Case, id=case_id)
    case.status = Case.CaseStatus.DELETE
    case.save()
    return HttpResponse() 
