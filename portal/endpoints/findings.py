
import io
import json
import shutil
import uuid
import numpy as np
import pydicom
from pathlib import Path
from urllib.request import urlopen

from django.http import HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction

from PIL import Image
import highdicom as hd

from portal.models import DICOMSet, Finding

from .common import json_load_body, user_opened_case

def sc_from_ref(reference_dataset, pixel_array):
    sc = hd.sc.SCImage.from_ref_dataset(
        ref_dataset=reference_dataset,
        pixel_array=pixel_array,
        photometric_interpretation=hd.PhotometricInterpretationValues.RGB,
        bits_allocated=8,
        coordinate_system=hd.CoordinateSystemNames.PATIENT,
        series_instance_uid=hd.UID(),
        sop_instance_uid=hd.UID(),
        series_number=getattr(reference_dataset, "SeriesNumber", 0),
        instance_number=getattr(reference_dataset, "InstanceNumber", 0),
        manufacturer="Gravis",
        pixel_spacing=None,
        patient_orientation=getattr(reference_dataset, "PatientOrientation", ("L", "P")),
    )
    # sc.ImageOrientationPatient = reference_dataset.ImageOrientationPatient
    # sc.SpacingBetweenSlices = reference_dataset.SpacingBetweenSlices
    # sc.ImagePositionPatient = reference_dataset.ImagePositionPatient
    sc.FrameOfReferenceUID = reference_dataset.FrameOfReferenceUID
    return sc


@login_required
def handle_finding(request, case, source_set, finding_id=None):
    dicom_set = DICOMSet.objects.get(id=int(source_set))
    if request.method == 'GET':
        results = []
        for set_ in dicom_set.case.dicom_sets.all():
            results += [f.to_dict() for f in set_.findings.all() if f.file_location]
        return JsonResponse(dict(findings=results))
    elif not user_opened_case(request,case):
        return HttpResponseForbidden()
    elif request.method == "DELETE":
        with transaction.atomic():
            finding = Finding.objects.get(id=finding_id)
            shutil.rmtree((Path(dicom_set.case.case_location) / finding.file_location).parent)
            finding.delete()
        return JsonResponse({})
    elif request.method == "PATCH":
        data = json_load_body(request)
        with transaction.atomic():
            finding = Finding.objects.get(id=finding_id)
            if name := data.get("name",None):
                finding.name = name
            if data := data.get("data",None):
                finding.data = data
            finding.save()
        return JsonResponse({})
    elif request.method == "POST":
        request_data = json_load_body(request)
        if "image_data" not in request_data:
            return HttpResponseBadRequest()
        
        with urlopen(request_data["image_data"]) as response:
            image_data = response.read()
        directory = Path(dicom_set.case.case_location) / "findings" / str(uuid.uuid4())
        directory.mkdir()
        filename = directory / f"finding.png"
        filename.touch()

        with open(filename,"wb") as f:
            f.write(image_data)
        
        im_frame = Image.open(io.BytesIO(image_data))
        im_array = np.array(im_frame.getdata(),dtype=np.uint8)[:,:3]
        im_array = im_array.reshape([*im_frame.size[::-1],3])
    
        related_instance = dicom_set.instances.first() # TODO: pick which instance?
        related_ds = pydicom.dcmread(Path(dicom_set.set_location) / related_instance.instance_location,stop_before_pixels=True)
        if "^" not in related_ds.PatientName:
            related_ds.PatientName = str(related_ds.PatientName) + "^"
        sc = sc_from_ref(related_ds,im_array)
        sc.save_as(directory / "finding.dcm")
        
        finding = Finding(
                created_by = request.user, 
                dicom_set = dicom_set,
                case = dicom_set.case,
                file_location = filename.relative_to(Path(dicom_set.case.case_location)),
                dicom_location = (directory / "finding.dcm").relative_to(Path(dicom_set.case.case_location)),
                # name = data.get("name",None),
                data = request_data.get("data",None)
                )
        finding.save()
        return JsonResponse(finding.to_dict())
    else:
        return HttpResponseNotAllowed(["POST","GET","PATCH", "DELETE"])