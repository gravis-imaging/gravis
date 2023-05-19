import json
import numpy as np
import pydicom
from pathlib import Path

from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from .common import get_im_orientation_mat, json_load_body
from portal.models import *


@login_required
@require_http_methods(["GET","POST"])
def volume_data(request, case, set):
    data = json_load_body(request)
    dicom_set = DICOMSet.objects.get(id=set)
    instances = dicom_set.instances
    example_instance = instances.first()
    metadata = json.loads(example_instance.json_metadata)
    im_orientation_mat = get_im_orientation_mat(metadata)

    for i, annotation in enumerate(data['annotations']):
        idx = np.abs(annotation['normal']).argmax()
        orientation = ['SAG','COR','AX'][idx]
        print(im_orientation_mat)
        handles_transformed = [ (np.linalg.inv(im_orientation_mat) @ handle_location).tolist() for handle_location in annotation["handles_indexes"] ]
        for h in handles_transformed:
            if orientation in ("SAG", "COR"):
                h[2] = -h[2]
            for n,v in enumerate(h):
                if v < 0:
                    h[n] = h[n]-1
                h[n] = int(h[n]) 

        slice_number = int(handles_transformed[0][idx])
        for h in range(len(handles_transformed)):
            handles_transformed[h] = handles_transformed[h][:idx]  + handles_transformed[h][idx+1:]
        print(slice_number)
        print(handles_transformed)
        instance = list(instances.order_by('slice_location').all())[slice_number]
        print(Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location)
        ds = pydicom.dcmread( Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location )
        pixel_array = ds.pixel_array
        value = None
        if annotation["tool"] == "EllipticalROI":
            [[_, top ], [_, bottom], [left, _], [right,_ ]] = handles_transformed
            subarray = pixel_array[top:bottom,left:right]
            # Mask out an ellipse
            def masked(in_array):
                # Not an entirely accurate ellipse especially for small ones
                ry, rx = map(lambda x: (x-1)/2.0,in_array.shape[0:2])
                y,x = np.ogrid[-ry: ry+1, -rx: rx+1]
                mask = (x / rx)**2+(y / ry)**2 > 1 
                v = in_array.view(np.ma.MaskedArray)
                v.mask = mask
                return v
            # show_array(subarray[0])
            subarray = subarray.astype('float32')
            value = np.ma.mean(masked(subarray))
        elif annotation["tool"] == "Probe":
            # handle = handles_absolute[0][1:]
            handle = handles_transformed[0]
            value = pixel_array[handle[1], handle[0]]
            value = value.item()
    return JsonResponse(dict(data=value))
        # annotation['normal']
    # processed_success.filter(case=case,type=f"CINE/AX",processing_job__dicom_set=source_set).latest('processing_job__created_at')