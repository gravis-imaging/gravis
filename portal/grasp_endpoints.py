import json
import logging
import os
from pathlib import Path
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from portal.models import *

logger = logging.getLogger(__name__)

@login_required
def grasp_metadata(request, case, study):
    series = DICOMInstance.objects.filter(study_uid=study, dicom_set__case=case).values('series_uid','acquisition_seconds').order_by('acquisition_seconds').distinct()
    result = [{
        "series_uid": k["series_uid"],
        "acquisition_seconds": k["acquisition_seconds"]
    } for k in series]
    return JsonResponse(result, safe=False)

@login_required
def preview_data(request, case, view, index):
    instance = DICOMInstance.objects.get(slice_location=index, dicom_set__case=case, dicom_set__type=f"CINE/{view.upper()}",dicom_set__processing_result__status="SUCCESS",dicom_set__processing_result__dicom_set__type="Incoming")
    loc = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to("/opt/gravis/data")
    result = ["wadouri:"+str(Path("/media") / loc) + f"?frame={n}" for n in range(instance.num_frames or 1)]

    # series = DICOMInstance.objects.filter(dicom_set__case=case, slice_location=index, 
    #         dicom_set__type=f"CINE/{view.upper()}",
    #         dicom_set__processing_result__status="SUCCESS",
    #         dicom_set__processing_result__dicom_set__type="Incoming",
    #     ).values('study_uid', 'instance_uid','series_uid','acquisition_seconds'
    #     ).order_by('acquisition_seconds'
    #     ).distinct()
    # result = [{
    #     "study_uid": k["study_uid"],
    #     "series_uid": k["series_uid"],
    #     "instance_uid": k["instance_uid"],
    #     "acquisition_seconds": k["acquisition_seconds"]
    # } for k in series]
    return JsonResponse(result, safe=False)
