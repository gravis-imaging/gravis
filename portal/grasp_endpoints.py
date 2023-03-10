import io
import json
import shutil
import uuid
import numpy as np
import pydicom
import os
from pathlib import Path
from urllib.request import urlopen

from django.http import HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

from PIL import Image
import highdicom as hd

from portal.models import *

cross = (lambda x,y:np.cross(x,y))

def show_array(a):
    print(f"""P2
{a.shape[1]} {a.shape[0]}
{a.max()}
"""+"\n".join(" ".join([str(k) for k in r]) for r in a))
# @login_required
# def grasp_metadata(request, case, study):
#     series = DICOMInstance.objects.filter(study_uid=study, dicom_set__case=case, dicom_set__type="ORI").values('series_uid','acquisition_seconds').order_by('acquisition_seconds').distinct()
#     result = [{
#         "series_uid": k["series_uid"],
#         "acquisition_seconds": k["acquisition_seconds"]
#     } for k in series]
#     return JsonResponse(result, safe=False)





# @login_required
# def preview_data(request, case, view, index):
#     instance = DICOMInstance.objects.get(slice_location=index, dicom_set__case=case, dicom_set__type=f"CINE/{view.upper()}",dicom_set__processing_job__status="Success",dicom_set__processing_job__dicom_set__origin="Incoming")
#     loc = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
#     result = ["wadouri:"+str(Path("/media") / loc) + f"?frame={n}" for n in range(instance.num_frames or 1)]
#     return JsonResponse(result, safe=False)
