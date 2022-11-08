import json
import logging
import os
from pathlib import Path
from time import sleep
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from portal.models import *

logger = logging.getLogger(__name__)

import pydicom
from django.views import static

@login_required
def grasp_metadata(request, case, study):
    series = DICOMInstance.objects.filter(study_uid=study, dicom_set__case=case).values('series_uid','acquisition_seconds').order_by('acquisition_seconds').distinct()
    result = [{
        "series_uid": k["series_uid"],
        "acquisition_seconds": k["acquisition_seconds"]
    } for k in series]
    return JsonResponse(result, safe=False)
