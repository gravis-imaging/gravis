
import json
import logging
import numpy as np
from pathlib import Path

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse, HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404
from portal.jobs.load_dicoms_job import CopyDicomsJob
from portal.models import *
from common.calculations import get_im_orientation_mat
from .common import user_opened_case, debug_sql
from django.db import transaction
from rq.registry import StartedJobRegistry, ScheduledJobRegistry 
import django_rq
from portal.jobs.fix_rotation_job import FixRotationJob

logger = logging.getLogger(__name__)


@login_required
@require_GET
def all_cases(request):
    '''
    Returns a JSON object containing information on all cases stored in the database.
    '''
    case_data = [case.to_dict(request.user.profile.privacy_mode) for case in Case.objects.all()]
    return JsonResponse({"data": case_data})

@login_required
@require_POST
@transaction.atomic
def delete_case(request, case):
    case = get_object_or_404(Case, id=case)

    # If someone else is viewing this case, don't mark for deletion.
    if not (case.last_read_by == request.user or (case.last_read_by is None and case.status==Case.CaseStatus.ERROR) or request.user.is_staff):
        return HttpResponseForbidden("You do not have permissions to delete this case.")

    case.status = Case.CaseStatus.DELETE
    case.save()
    return HttpResponse() 

@login_required
@require_POST
def reprocess_case(request, case):
    case = get_object_or_404(Case, id=case)

    if not (case.last_read_by == request.user or (case.last_read_by is None and case.status==Case.CaseStatus.ERROR) or request.user.is_staff):
        return HttpResponseForbidden("Cannot reprocess a case that you haven't opened.")

    if not request.user.has_perm("portal.reprocess"):
        return HttpResponseForbidden("Insufficient permissions.")

    if case.get_running_jobs():
        return JsonResponse(dict(error="a job is already queued or running"), status=503)

    directory = Path(case.case_location) / "input"
    with open(directory / "study.json","r") as f:
        study_json = json.load(f)

    study_json["tags"] = [tag.name for tag in case.tags.all()]

    CopyDicomsJob.enqueue_work(case=None,parameters=dict(incoming_folder=str(directory), study_json=study_json))

    return HttpResponse() 

@login_required
@require_POST
def rotate_case(request, case, n):
    case = get_object_or_404(Case, id=case)
    if not request.user.has_perm("portal.rotate"):
        return HttpResponseForbidden("Insufficient permissions.")

    if ( case.status == Case.CaseStatus.COMPLETE ):
        return HttpResponseBadRequest("Cannot modify a case that is already Complete.")

    if (not (
            case.last_read_by == request.user # user opened this case
            or (case.last_read_by is None and case.status==Case.CaseStatus.ERROR) # Nobody opened this case, it's in an error state
            or request.user.is_staff # User is staff, assume knows what they're doing
        )):
        return HttpResponseForbidden("Cannot rotate a case that you haven't opened.")
    
    if case.get_running_jobs():
        return JsonResponse(dict(error="a job is already queued or running"), status=503)

    job,_ = FixRotationJob.enqueue_work(case=case,parameters=dict(n=n), error_case_ok=True)

    return JsonResponse(dict(id=job.id)) 

@login_required
@require_GET
def jobs_running(request, case):
    case = get_object_or_404(Case, id=case)

    if case.get_running_jobs():
        return JsonResponse(dict(result=True))
    return JsonResponse(dict(result=False))
    

@login_required
@require_GET
def get_case(request, case):
    '''
    Returns information about the given case in JSON format. Returns 404 page if
    case ID does not exist
    '''
    case = get_object_or_404(Case, id=case)
    case_dict = case.to_dict(request.user.profile.privacy_mode)
    return JsonResponse(case_dict)

@login_required
@require_POST
@transaction.atomic
def set_case_status(request, case, new_status):
    case_item = get_object_or_404(Case, id=case)

    # Don't set the case status unless this user opened it or is staff
    if not (case_item.last_read_by.id == request.user.id or request.user.is_staff):
        return HttpResponseForbidden()

    if case_item.status not in [Case.CaseStatus.VIEWING, Case.CaseStatus.READY, Case.CaseStatus.COMPLETE]:
        return HttpResponseForbidden()
    case_item.viewed_by = None

    if new_status == "ready":
        case_item.status = Case.CaseStatus.READY
        case_item.save()
    elif new_status == "complete":
        case_item.status = Case.CaseStatus.COMPLETE
        case_item.save()
    else:
        return HttpResponseBadRequest()

    return HttpResponse() 


@login_required
@require_GET
@transaction.atomic
def get_case_viewable(request, case):
    case_item = get_object_or_404(Case, id=case)
    if case_item.status in (Case.CaseStatus.READY, Case.CaseStatus.COMPLETE, Case.CaseStatus.VIEWING, Case.CaseStatus.ERROR) or request.user.is_staff:
        return JsonResponse({"ok":True})
    return JsonResponse({"ok":False})

@login_required
@require_POST
@transaction.atomic
def set_case_viewing(request, case):
    case = get_object_or_404(Case, id=case)
    if case.status not in (Case.CaseStatus.READY, Case.CaseStatus.COMPLETE, Case.CaseStatus.VIEWING):
        return JsonResponse({"ok":False})

    if ( case.status == Case.CaseStatus.VIEWING and case.viewed_by != request.user ):
        return JsonResponse({"ok":False})

    case.viewed_by = request.user
    case.last_read_by = request.user
    case.status = Case.CaseStatus.VIEWING
    case.save()
    return JsonResponse({"ok":True})

@login_required
@require_GET
def case_metadata(request, case, dicom_set, study=None):
    fields = ["series_uid","series_number", "slice_location", "acquisition_number", "acquisition_seconds"]

    q = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set=dicom_set)
    if study:
        q = q.filter(study_uid=study)
    series = q.values(*fields).order_by('series_uid').distinct('series_uid').all()
    
    result = [{
        f:k[f] for f in fields
    } for k in sorted(list(series),
        key=lambda x:(x.get('acquisition_number',0), x.get('series_number',0),x.get('slice_location',0)))
    ]
    return JsonResponse(result, safe=False)

@login_required
@require_GET
def processed_results_json(request, case, category, source_set):
    # fields = ["series_number", "slice_location", "acquisition_number"]
    # slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    job = ProcessingJob.successful.filter(case_id=int(case), dicom_set=source_set, category=category).latest("created_at")
    return JsonResponse(dict(result = job.json_result))


@login_required
@require_GET
def preview_urls(request, case, source_set, view, location):
    dicom_set = DICOMSet.processed_success.filter(case_id=int(case),type=f"CINE/{view}").filter(processing_job__dicom_set=source_set).latest('processing_job__created_at')
    location = np.asarray(list(map(int, location.split(","))))
    im_orientation_mat_inv = np.asarray(DICOMSet.objects.get(case_id=int(case),type=f"ORI").image_orientation_calc_inv) # get_im_orientation_mat(json.loads(representative_instance.json_metadata))

    transformed_location = (im_orientation_mat_inv @ location)
    slice_number = int(transformed_location[ [ "SAG", "COR", "AX"].index(view) ])
    qs = dicom_set.instances.only("slice_location","instance_location","num_frames","dicom_set_id").order_by('slice_location')
    if slice_number < 0:
        slice_number = -slice_number # would expect this to be 1 - slice_number but there's an off-by-one issue somewhere
        qs = qs.reverse()
    instance = qs[slice_number]

    location = (Path(dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
    wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
    return JsonResponse(dict(urls=[ wado_uri +f"?frame={n}" for n in range(instance.num_frames+1)]))


@login_required
@require_GET
def processed_results_urls(request, case, set_type, source_set):
    fields = ["series_number", "slice_location", "acquisition_number", "acquisition_seconds"]
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_set = DICOMSet.processed_success.filter(case_id=int(case),type=set_type, processing_job__dicom_set=source_set).latest('processing_job__created_at')
    instances = dicom_set.instances.filter(**slices_lookup).only("instance_location","num_frames","dicom_set_id").order_by("acquisition_seconds", "slice_location","instance_location","series_number") # or "instance_number"

    urls = []
    for instance in instances:
        location = (Path(dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
        wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
        if (instance.num_frames or 1) > 1:
            urls.extend( [ wado_uri +f"?frame={n}" for n in range(instance.num_frames)])
        else:
            urls.append(wado_uri)
    return JsonResponse(dict(urls=urls, set_id = dicom_set.id))


@login_required
@require_GET
def mip_metadata(request, case, source_set):
    fields = ["series_number", "slice_location", "acquisition_number", "acquisition_seconds"]
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_sets = DICOMSet.processed_success.filter(case_id=int(case),type="MIP", processing_job__dicom_set=source_set)
    instances = dicom_sets.latest('processing_job__created_at').instances.filter(**slices_lookup).only("slice_location","dicom_set_id").order_by("acquisition_seconds", "slice_location","instance_location","series_number") # or "instance_number"

    details = []
    for instance in instances:
        details.append(dict(slice_location=instance.slice_location, id=instance.id))
    return JsonResponse(dict(details=details))

@login_required
@require_GET
def logs(request, case):
    if not (request.user.is_staff):
        return HttpResponseForbidden()
    case = get_object_or_404(Case, id=case)
    return JsonResponse(dict(logs=[(x.stem, str(x.relative_to(settings.DATA_FOLDER))) for x in (Path(case.case_location) / "logs").glob("*.log")]))