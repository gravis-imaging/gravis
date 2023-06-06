import json
import logging
import os
from pathlib import Path
from time import sleep
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.staticfiles import views as static_views
from django.views import static

import django_rq
import docker
import pydicom
import numpy as np

from portal.models import *
from portal.views import serve_media

logger = logging.getLogger(__name__)


@login_required
def retrieve_instance(request, study, series, instance, case, frame=1):
    if frame != 1:
        return HttpResponse(status=500)
    instance = DICOMInstance.objects.only("instance_location","dicom_set__set_location").select_related("dicom_set").get(
        study_uid=study, series_uid=series, instance_uid=instance, dicom_set__case=case
    )
    data_path = Path(instance.dicom_set.set_location) / instance.instance_location
    file_location = data_path.relative_to(settings.DATA_FOLDER)
    return serve_media(request,file_location)


@login_required
@require_http_methods(["POST"])
def test_populate_instances(request):
    """
    For testing, populate list of available instances and get their metadata
    """
    data_folder = Path(settings.DATA_FOLDER)
    for k in data_folder.glob("**/*"):
        if not k.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(k), stop_before_pixels=True)
        except:
            continue
        k = DICOMInstance.objects.update_or_create(
            study_uid=ds.StudyInstanceUID,
            series_uid=ds.SeriesInstanceUID,
            instance_uid=ds.SOPInstanceUID,
            defaults=dict(
                json_metadata=ds.to_json(),
                file_location=str(k.relative_to(data_folder)),
                study_description=ds.get("StudyDescription"),
                series_description=ds.get("SeriesDescription"),
                patient_name=ds.get("PatientName"),
            ),
        )
    return HttpResponse("Done!")


@login_required
def study_metadata(request, case, study):
    instances = DICOMInstance.objects.filter(study_uid=study, dicom_set__case=case)
    metadatas = [i.json_metadata for i in instances]
    data = "[" + ",".join(metadatas) + "]"

    return HttpResponse(data, content_type="application/json")


@login_required
def series_metadata(request, case, study, series):
    instances = DICOMInstance.objects.filter(study_uid=study, series_uid=series, dicom_set__case=case)
    metadatas = [json.loads(k.json_metadata) for k in instances]
   
    # Sort the results in spatial order.
    im_orientation_patient = np.asarray(metadatas[0]["00200037"]["Value"]).reshape((2,3))
    metadatas = sorted(metadatas, key = lambda x:np.dot(np.cross(*im_orientation_patient),np.asarray(x["00200032"]["Value"])))

    return JsonResponse(metadatas, safe=False)


@login_required
def instance_metadata(request, case, study, series, instance):
    instances = DICOMInstance.objects.filter(
        study_uid=study, series_uid=series, instance_uid=instance, dicom_set__case=case
    )
    metadatas = [json.loads(k.json_metadata) for k in instances]
    return JsonResponse(metadatas, safe=False)
