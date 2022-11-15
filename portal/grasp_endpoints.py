import json
from loguru import logger
import os
from pathlib import Path
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from portal.models import *


# @login_required
# def grasp_metadata(request, case, study):
#     series = DICOMInstance.objects.filter(study_uid=study, dicom_set__case=case, dicom_set__type="ORI").values('series_uid','acquisition_seconds').order_by('acquisition_seconds').distinct()
#     result = [{
#         "series_uid": k["series_uid"],
#         "acquisition_seconds": k["acquisition_seconds"]
#     } for k in series]
#     return JsonResponse(result, safe=False)


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
def processed_results_urls(request, case, case_type, source_set=None):
    fields = ["series_number", "slice_location", "acquisition_number"]
    case = Case.objects.get(id=int(case))
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_set = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=case_type)
    if source_set:
        dicom_set = dicom_set.filter(processing_job__dicom_set=source_set)
    instances = dicom_set.latest('processing_job__created_at').instances.filter(**slices_lookup)

    urls = []
    for instance in instances:
        location = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
        wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
        if (instance.num_frames or 1) > 1:
            urls.extend( [ wado_uri +f"?frame={n}" for n in range(instance.num_frames)])
        else:
            urls.append(wado_uri)
    return JsonResponse(dict(urls=urls))

# @login_required
# def preview_data(request, case, view, index):
#     instance = DICOMInstance.objects.get(slice_location=index, dicom_set__case=case, dicom_set__type=f"CINE/{view.upper()}",dicom_set__processing_job__status="Success",dicom_set__processing_job__dicom_set__origin="Incoming")
#     loc = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
#     result = ["wadouri:"+str(Path("/media") / loc) + f"?frame={n}" for n in range(instance.num_frames or 1)]
#     return JsonResponse(result, safe=False)
