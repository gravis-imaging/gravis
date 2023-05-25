from collections import defaultdict
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

class SkipDicomSet(Exception):
    pass
class WrongFrameOfReference(SkipDicomSet):
    pass

@login_required
@require_http_methods(["GET","POST"])
def volume_data(request, case, set):
    data = json_load_body(request)
    # dicom_set = DICOMSet.objects.get(id=set)

    if data.get('frame_of_reference') is None:
        sets = [DICOMSet.objects.get(id=set)]
    else:
        sets = DICOMSet.objects.filter(case=case).exclude(type__in=("ORI", "SUB", "CINE/AX","CINE/COR", "CINE/SAG")).order_by("type").distinct("type")

    result = {}
    for s in sets:
        try:
            result[s.type] = get_stats(data['annotations'], s, data.get('frame_of_reference'))
        except SkipDicomSet: 
            pass
    # print(result)
    final_result = defaultdict(dict)
    for set_type in result:
        for label in result[set_type]:
            final_result[label][set_type] = result[set_type][label]
    return JsonResponse(final_result)


def show_array(a):
    print(f"""P2
{a.shape[1]} {a.shape[0]}
{a.max()}
"""+"\n".join(" ".join([str(k) for k in r]) for r in a))

def get_stats(annotations, dicom_set, frame_of_reference=None):
    # print(dicom_set.type)
    instances = dicom_set.instances
    example_instance = instances.representative()
    metadata = json.loads(example_instance.json_metadata)
    # print(dicom_set.type, frame_of_reference, metadata.get("00200052",{}).get("Value"))
    if frame_of_reference:
        if metadata.get("00200052",{}).get("Value",[None])[0] != frame_of_reference:
            raise WrongFrameOfReference()
    im_orientation_mat = get_im_orientation_mat(metadata)
    
    def get_position(instance):
        return np.asarray(json.loads(instance.json_metadata)["00200032"]["Value"])

    instances_sorted = sorted(instances.all(), key=lambda x:np.dot(im_orientation_mat[2],get_position(x)))

    volume = None
    for i, instance in enumerate(instances_sorted):
        dcm = pydicom.dcmread(Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location)
        array = dcm.pixel_array # [ row, column ] order
        if len(array.shape) > 2:
            raise SkipDicomSet() # Probably a color image
        
        if volume is None:
            volume = np.empty_like(array,shape=(len(instances_sorted), *array.shape))
        volume[i,:,:] = array

    def get_index(axis,volume_slice):
            return [(volume_slice,        slice(None),  slice(None)), # axial 
                    (slice(None,None,-1), volume_slice, slice(None)), # coronal
                    (slice(None,None,-1), slice(None),  volume_slice) # sagittal
            ][axis]
    
    results = {}
    for i, annotation in enumerate(annotations):
        idx = np.abs(annotation['normal']).argmax()
        orientation = ['SAG','COR','AX'][idx]
        # print(orientation)
        # print(im_orientation_mat)
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
        # print("Slice number", slice_number)
        # print("index", get_index(2-idx,slice_number))
        # print(handles_transformed)

        
        pixel_array = volume[get_index(2-idx,slice_number)]
        # show_array(pixel_array[::2,::2])
        # ds = pydicom.dcmread( Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location )
        # pixel_arrcy = ds.pixel_array
        # print(ds.pixel_array.shape)
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
        results[annotation['label']] = value
    return results
    # return JsonResponse(dict(data=value))
        # annotation['normal']
    # processed_success.filter(case=case,type=f"CINE/AX",processing_job__dicom_set=source_set).latest('processing_job__created_at')