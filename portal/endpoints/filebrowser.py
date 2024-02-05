import json
import shutil
import os
from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
import pydicom
from portal.jobs.load_dicoms_job import CopyDicomsJob

from portal.models import *
from pathlib import Path
from django.conf import settings

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


class SubmitForm(forms.Form):
     patient_name = forms.CharField(label='Patient Name', max_length=100)
     mrn = forms.CharField(label='MRN', max_length=100)
     acc = forms.CharField(label='Accession', max_length=100)
     study_description = forms.CharField(label='Study Description', max_length=100,disabled=True, required=False)
     num_spokes = forms.IntegerField(label='Num spokes', min_value=0)
     case_type = forms.ChoiceField(choices=[("GRASP MRA","GRASP MRA"), ("GRASP Onco","GRASP Onco"),("Series Viewer","Series Viewer")])


def resolve_path(name,path):
    for d in settings.BROWSER_BASE_DIRS:
        if d["name"] == name:
            top_dir_name = Path(d["name"])
            top_dir = Path(d["location"])
            break
    else:
        raise Exception()
    full_path = top_dir / path
    if not full_path.is_dir():
        raise Exception(f"{full_path} is not a directory.")
    if not full_path.is_relative_to(top_dir):
        raise Exception(f"{full_path} is not a proper subdirectory.")
    
    return full_path, top_dir, top_dir_name


@login_required
def case_directory(request, name, path):
    try:
        full_path, _, _ = resolve_path(name,path)
    except:
        return HttpResponseBadRequest()
    
    try:
        first = next(full_path.glob("*.dcm"))
    except:
         return JsonResponse(dict(case_info=dict(patient_name="",acc="", patient_id="",study_description="")))
    ds = pydicom.dcmread(first,defer_size ='1 KB', stop_before_pixels=True)

    if (study_json := full_path / "study.json").exists():
        case_info = json.load(study_json.open("r"))
        case_info["study_description"] = ds.StudyDescription
    else:
        def getstr(k):
            return str(ds.get(k,""))
        case_info=dict(patient_name=getstr("PatientName"),acc=getstr("AccessionNumber"), patient_id=getstr("PatientID"),study_description=getstr("StudyDescription"))

    return JsonResponse(dict(case_info = case_info))
    

@login_required
def submit_directory(request, name, path):
    try:
        full_path,_,_ = resolve_path(name,path)
    except:
        return HttpResponseBadRequest()
    form = SubmitForm(request.POST)
        # check whether it's valid:
    if not form.is_valid():
        return HttpResponseBadRequest(json.dumps(dict(validation_errors=form.errors)))

    _, _, free = shutil.disk_usage(settings.CASES_FOLDER)
    path_size = sum(f.stat().st_size for f in full_path.glob('**/*') if f.is_file())
    if free < 4*path_size:
        return HttpResponse("Insufficient disk space available.", status=507)

    study_json = dict(
        patient_name=form.cleaned_data["patient_name"],
        mrn=form.cleaned_data["mrn"],
        acc=form.cleaned_data["acc"],
        num_spokes=form.cleaned_data["num_spokes"],
        case_type=form.cleaned_data["case_type"],
        status="",
        reader="",
    )
    CopyDicomsJob.enqueue_work(case=None,parameters=dict(incoming_folder=str(full_path), study_json=study_json))

    return redirect("/filebrowser")
    # study_json = {}


@login_required
def list_directory(request, name=None, path=None):
    if name == None:
        return JsonResponse(dict(up_path="/",listing=[dict(location=d["name"], name=d["name"], is_dir=True) for d in settings.BROWSER_BASE_DIRS]))
    if path == None:
        path = Path(".")
    else:
        path = Path(path)

    full_path, top_dir, top_dir_name = resolve_path(name, path)

    response = []
    dicoms = []
    skipped_dicoms = False
    relative_path = str(full_path.relative_to(top_dir))
    for dir_entry in os.scandir(full_path):
        # Path.iterdir() is noticably slow on very large directories.
        is_dir = dir_entry.is_dir()
        is_dcm = dir_entry.name.endswith(".dcm")
        if not (is_dir or is_dcm or dir_entry.name.startswith('.')):
            continue
        # location = str( top_dir_name / Path(dir_entry.path).relative_to(top_dir))
        if relative_path==".":
            location = f"{top_dir_name}/{dir_entry.name}"
        else:
            location = f"{top_dir_name}/{relative_path}/{dir_entry.name}"
            
        info = dict(is_dir=is_dir, location=location, name=dir_entry.name)
        if is_dcm:
            dicoms.append(info)
        else:
            response.append(info)
    response = sorted(response, key= lambda x:x.get('location'))
    dicoms = sorted(dicoms, key= lambda x:x.get('location'))
    if len(dicoms) < 50:
        response.extend(dicoms)
    else:
        name = ", ".join(d["name"] for d in dicoms[0:3]) + " ... "
        if skipped_dicoms:
            name += f"(> {len(dicoms)})"
        else:
            name += dicoms[-1]["name"] + f" ({len(dicoms)})"
        response.append(dict(is_dir=False, location="", name=name))

    if (p := full_path / "study.json").exists():
        response.append(dict(is_dir=False, location =  str( top_dir_name / p.relative_to(top_dir)),name='study.json', num_dicoms = len(dicoms) ))

    up_path = "/"+str((top_dir_name / path).parent)
    if up_path == "/.":
        up_path = "/"
    return JsonResponse(dict(up_path=up_path,listing=response))

