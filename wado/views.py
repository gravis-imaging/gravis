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
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from portal.models import *
import django_rq
import docker

logger = logging.getLogger(__name__)
from django.contrib.staticfiles import views as static_views

import pydicom
from django.views import static


@login_required
def retrieve_instance(request, study, series, instance, frame=1):
    if frame != 1:
        return HttpResponse(status_code=500)
    instance = DICOMInstance.objects.get(
        study_uid=study, series_uid=series, instance_uid=instance
    )

    file_location = Path(instance.dicom_set.set_location) / instance.instance_location
    file_location = file_location.relative_to(settings.DATA_FOLDER)

    if "localhost" in request.headers["Host"] or "127.0.0.1" in request.headers["Host"]:
        # We're not running behind nginx so we are going to just serve the file ourselves.
        response = static.serve(
            request,
            file_location,
            document_root=settings.DATA_FOLDER,
        )
        return response

    return HttpResponse(
        headers={
            "X-Accel-Redirect": str(Path("/secret") / file_location),
        }
    )


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
