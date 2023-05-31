
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
from django.conf import settings
from django.db import connection

from PIL import Image
import highdicom as hd
from .common import debug_sql
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
    dicom_set = DICOMSet.objects.only("set_location","case__id","case__case_location","case__status","case__viewed_by_id").select_related("case").get(id=int(source_set))
    case = dicom_set.case
    if request.method == 'GET':
        results = [f.to_dict() for f in case.findings.all()]
        return JsonResponse(dict(findings=results))
    elif not user_opened_case(request,case):
        return HttpResponseForbidden()
    elif request.method == "DELETE":
        with transaction.atomic():
            finding = Finding.objects.only("file_location").get(id=finding_id)
            shutil.rmtree((Path(case.case_location) / finding.file_location).parent)
            finding.delete()
        return JsonResponse({})
    elif request.method == "PATCH":
        data = json_load_body(request)
        with transaction.atomic():
            finding = Finding.objects.filter(id=finding_id)
            values = {}
            if name := data.get("name",None):
                values['name'] = name
            if data := data.get("data",None):
                values['data'] = data
            finding.update(**values)
        return JsonResponse({})
    elif request.method == "POST":
        request_data = json_load_body(request)
        if "image_data" not in request_data:
            return HttpResponseBadRequest()
        
        with urlopen(request_data["image_data"]) as response:
            image_data = response.read()
        directory = Path(case.case_location) / "findings" / str(uuid.uuid4())
        directory.mkdir()
        filename = directory / f"finding.png"
        filename.touch()

        with open(filename,"wb") as f:
            f.write(image_data)
        
        im_frame = Image.open(io.BytesIO(image_data))
        im_array = np.array(im_frame.getdata(),dtype=np.uint8)[:,:3]
        im_array = im_array.reshape([*im_frame.size[::-1],3])
        # Just tries to get an arbitrary instance. 
        # This seemed to be slow for some reason, not sure why, replacing with raw sql for now
        # TODO: pick the "first" instance?
        # related_instance = dicom_set.instances.representative() # This should do the same thing. 
        # These are faster but not as fast.
        # instance = DICOMInstance.objects.raw("select id, instance_location from gravis_dicom_instance where dicom_set_id = %s limit 1", [int(source_set)])[0]
        # instance = dicom_set.instances.only("instance_location")[:1].get() # TODO: pick which instance?
        # instance_location = instance.instance_location
        # Alternatively, dicom_set.instances.all()[:1].values("instance_location")[0]['instance_location']
        c = connection.cursor()
        c.execute("select instance_location from gravis_dicom_instance where dicom_set_id = %s limit 1",[int(source_set)])
        instance_location = c.fetchone()[0]
        c.close()

        related_ds = pydicom.dcmread(Path(dicom_set.set_location) / instance_location,stop_before_pixels=True)
        if "^" not in related_ds.PatientName:
            related_ds.PatientName = str(related_ds.PatientName) + "^"
        sc = sc_from_ref(related_ds,im_array)
        sc.save_as(directory / "finding.dcm")
        
        finding = Finding(
                created_by = request.user, 
                dicom_set = dicom_set,
                case = case,
                file_location = filename.relative_to(Path(case.case_location)),
                dicom_location = (directory / "finding.dcm").relative_to(Path(case.case_location)),
                # name = data.get("name",None),
                data = request_data.get("data",None)
                )
        finding.save()
        return JsonResponse(finding.to_dict())
    else:
        return HttpResponseNotAllowed(["POST","GET","PATCH", "DELETE"])
