import json
import logging
import os
from pathlib import Path
from time import sleep
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import connections
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.http import JsonResponse

from portal.models import *
import django_rq
import docker

logger = logging.getLogger(__name__)
from django.contrib.staticfiles import views as static_views

import pydicom


@login_required
def retrieve_instance(request, study, series, instance, frame=1):
    if frame != 1:
        return HttpResponse(status_code=500)
    instance = DICOMInstance.objects.get(
        study_uid=study, series_uid=series, instance_uid=instance
    )
    return HttpResponse(
        headers={
            "X-Accel-Redirect": "/secret/" + instance.file_location,
            "Content-Type": "application/octet-stream",
        }
    )


@login_required
def test(request):
    """
    For testing, populate list of available instances and get their metadata
    """
    data_folder = Path(settings.DATA_FOLDER)
    for k in data_folder.glob("**/*"):
        if not k.is_file():
            continue
        ds = pydicom.dcmread(str(k), stop_before_pixels=True)
        # ds.TransferSyntaxUID = "1.2.840.10008.1.2"

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
    return JsonResponse({"ok": True}, safe=False)


@login_required
def study_metadata(request, study):
    instances = DICOMInstance.objects.filter(study_uid=study)
    metadatas = [json.loads(k.json_metadata) for k in instances]
    return JsonResponse(metadatas, safe=False)


@login_required
def series_metadata(request, study, series):
    instances = DICOMInstance.objects.filter(study_uid=study, series_uid=series)
    metadatas = [json.loads(k.json_metadata) for k in instances]
    return JsonResponse(metadatas, safe=False)


@login_required
def instance_metadata(request, study, series, instance):
    instances = DICOMInstance.objects.filter(
        study_uid=study, series_uid=series, instance_uid=instance
    )
    metadatas = [json.loads(k.json_metadata) for k in instances]
    return JsonResponse(metadatas, safe=False)
