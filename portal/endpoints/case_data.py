
import json
import numpy as np
from pathlib import Path

from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse, HttpResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404
from portal.models import *
from .common import get_im_orientation_mat

@login_required
@require_GET
def all_cases(request):
    '''
    Returns a JSON object containing information on all cases stored in the database.
    '''
    case_data = [case.to_dict(request.user.profile.privacy_mode) for case in Case.objects.all()]
    return JsonResponse({"data": case_data}, safe=False)


@login_required
@require_POST
def delete_case(request, case):
    case = get_object_or_404(Case, id=case)
    case.status = Case.CaseStatus.DELETE
    case.save()
    return HttpResponse() 


@login_required
@require_GET
def get_case(request, case):
    '''
    Returns information about the given case in JSON format. Returns 404 page if
    case ID does not exist
    '''
    case = get_object_or_404(Case, id=case)
    json_data = case.to_dict(request.user.profile.privacy_mode)
    return JsonResponse(json_data, safe=False)


@login_required
@require_POST
def set_case_status(request, case, new_status):
    case = get_object_or_404(Case, id=case)

    if case.status != Case.CaseStatus.VIEWING:
        return HttpResponseForbidden()
    
    if case.viewed_by != request.user and not request.user.is_staff:
        return HttpResponseForbidden()

    case.viewed_by = None;

    if new_status=="ready":
        case.status = Case.CaseStatus.READY
        case.save()
    elif new_status=="complete":
        case.status = Case.CaseStatus.COMPLETE
        case.save()
    else:
        return HttpResponseBadRequest()

    return HttpResponse() 


@login_required
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
def processed_results_json(request, case, category, source_set):
    # fields = ["series_number", "slice_location", "acquisition_number"]
    case = Case.objects.get(id=int(case))
    # slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    job = ProcessingJob.successful.filter(case=case, dicom_set=source_set, category=category).latest("created_at")
    return JsonResponse(dict(result = job.json_result))


@login_required
def preview_urls(request, case, source_set, view, location):
    case = Case.objects.get(id=int(case))
    dicom_set = DICOMSet.processed_success.filter(case=case,type=f"CINE/{view}").filter(processing_job__dicom_set=source_set)

    location = np.asarray(list(map(int, location.split(","))))

    instances = dicom_set.latest('processing_job__created_at').instances.order_by("slice_location").all()
    im_orientation_mat = get_im_orientation_mat(json.loads(instances[0].json_metadata))
    # im_orientation_patient = np.asarray(json.loads(instances[0].json_metadata)["00200037"]["Value"]).reshape((2,3))
    # im_orientation_mat = np.rint(np.vstack((im_orientation_patient,[cross(*im_orientation_patient)])))

    # print(location)
    transformed_location = (np.linalg.inv(im_orientation_mat) @ location)
    # print(transformed_location)
    slice_number = int(transformed_location[ [ "SAG", "COR", "AX"].index(view) ])
    if slice_number < 0:
        slice_number -= 1
    instance = list(instances)[slice_number]

    location = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
    wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
    return JsonResponse(dict(urls=[ wado_uri +f"?frame={n}" for n in range(instance.num_frames)]))


@login_required
def processed_results_urls(request, case, case_type, source_set):
    fields = ["series_number", "slice_location", "acquisition_number", "acquisition_seconds"]
    case = Case.objects.get(id=int(case))
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_set = DICOMSet.processed_success.filter(case=case,type=case_type, processing_job__dicom_set=source_set)
    instances = dicom_set.latest('processing_job__created_at').instances.filter(**slices_lookup).order_by("acquisition_seconds", "slice_location","instance_location","series_number") # or "instance_number"

    urls = []
    for instance in instances:
        location = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
        wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
        if (instance.num_frames or 1) > 1:
            urls.extend( [ wado_uri +f"?frame={n}" for n in range(instance.num_frames)])
        else:
            urls.append(wado_uri)
    return JsonResponse(dict(urls=urls))


@login_required
def mip_metadata(request, case, source_set):
    fields = ["series_number", "slice_location", "acquisition_number", "acquisition_seconds"]
    case = Case.objects.get(id=int(case))
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_sets = DICOMSet.processed_success.filter(case=case,type="MIP", processing_job__dicom_set=source_set)
    instances = dicom_sets.latest('processing_job__created_at').instances.filter(**slices_lookup).order_by("acquisition_seconds", "slice_location","instance_location","series_number") # or "instance_number"

    details = []
    for instance in instances:
        details.append(dict(slice_location=instance.slice_location))
    return JsonResponse(dict(details=details))
