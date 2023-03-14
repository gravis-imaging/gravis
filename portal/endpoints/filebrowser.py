import json

from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed, HttpResponseNotFound, JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import pydicom

from portal.models import *
from pathlib import Path

top_dirs = [dict(name="root_vagrant", location="/vagrant"), dict(name="home_vagrant",location="/home/vagrant")]

from django import forms


# {
#         "patient_name":"TEST^MIP",
#         "mrn":"87654321",
#         "acc":"0",
#         "case_type":"GRASP MRA",
#         "received":"1900-01-01 00:00",
#         "status":"",
#         "reader":"",
#         "exam_time":"1900-01-01 00:00",
#         "twix_id": "asdf",
#         "num_spokes": 4
# }
@login_required
def case_directory(request, name, path):
    for d in top_dirs:
        if d["name"] == name:
            top_dir_name = Path(d["name"])
            top_dir = Path(d["location"])
            break
    else:
        return HttpResponseBadRequest()
    full_path = top_dir / path
    if not full_path.is_dir():
        return HttpResponseNotFound()

    first = next(full_path.glob("*.dcm"))
    ds = pydicom.dcmread(first,defer_size ='1 KB', stop_before_pixels=True)
    return JsonResponse(dict(case_info=dict(patient_name=str(ds.PatientName),accession=str(ds.AccessionNumber), patient_id=str(ds.PatientID),study_description=str(ds.StudyDescription))))
    

@login_required
def list_directory(request, name=None, path=None):
    if name == None:
        return JsonResponse(dict(up_path="/",listing=[dict(location=d["name"], name=d["name"], is_dir=True) for d in top_dirs]))
    if path == None:
        path = Path(".")
    else:
        path = Path(path)

    for d in top_dirs:
        if d["name"] == name:
            top_dir_name = Path(d["name"])
            top_dir = Path(d["location"])
            break
    else:
        return HttpResponseBadRequest()

    full_path = top_dir / path
    if not full_path.is_dir():
        return HttpResponseNotFound()
    
    if not full_path.is_relative_to(top_dir):
        return HttpResponseBadRequest()
    
    response = []
    dicoms = []
    skipped_dicoms = False
    for p in full_path.iterdir():
        if not (p.is_dir() or p.suffix == '.dcm') or p.name.startswith('.'):
            continue
        location = str( top_dir_name / p.relative_to(top_dir))
        info = dict(is_dir=p.is_dir(), location=location, name=p.name)
        if p.suffix == ".dcm":
            dicoms.append(info)
            if len(dicoms) >= 500:
                skipped_dicoms = True
                break
        else:
            response.append(info)
    if len(dicoms) < 50:
        response.extend(dicoms)
    else:
        name = ", ".join(d["name"] for d in dicoms[0:3]) + " ... "
        if skipped_dicoms:
            name += f"(> {len(dicoms)})"
        else:
            name += dicoms[-1]["name"] + f" ({len(dicoms)})"
        response.append(dict(is_dir=False, location="", name=name))
    up_path = "/"+str((top_dir_name / path).parent)
    if up_path == "/.":
        up_path = "/"
    return JsonResponse(dict(up_path=up_path,listing=response))

