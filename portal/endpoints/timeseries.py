import gzip
import json
import numpy as np
import pydicom
from pathlib import Path

from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from common.calculations import get_im_orientation_mat
from .common import json_load_body
from portal.models import *

@login_required
@require_http_methods(["GET","POST"])
def timeseries_data(request, case, source_set):
    data = json_load_body(request)
    # averages = np.zeros((120,1+len(data['annotations'])))
    # averages[:,0] = np.asarray(range(120))
    averages = []
    
    chart_options = data.get('chart_options',{})        
    mode = chart_options.get('mode','mean')
    summary_method = dict(mean=np.ma.mean,
                median=np.ma.median,
                ptp=np.ma.ptp)[mode]
    
    acquisition_seconds = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set=source_set).values("acquisition_seconds").distinct("acquisition_seconds").order_by("acquisition_seconds")
    acquisition_timepoints = [k['acquisition_seconds'] for k in acquisition_seconds]
    
    im_orientation_mat_inv = np.asarray(DICOMSet.objects.get(type="ORI",case=case).image_orientation_calc_inv)

    dicom_sets_by_orientation = {}
    # TODO: Calculate out-of-bounds properly. It's checked on the client, but still...
    for annotation in data['annotations']:
        idx = np.abs(annotation['normal']).argmax()
        o = ['SAG','COR','AX'][idx]
        annotation['orientation'] = o
        if o not in dicom_sets_by_orientation:
            dicom_sets_by_orientation[o] = DICOMSet.processed_success.filter(case=case,type=f"CINE/{o}",processing_job__dicom_set=source_set).only("id").latest('processing_job__created_at')
    slice_cache = {}

    for annotation in data['annotations']:
        idx = np.abs(annotation['normal']).argmax()
        orientation = annotation['orientation']
        dicom_set = dicom_sets_by_orientation[orientation]
        handles_transformed = [ (im_orientation_mat_inv @ handle_location).tolist() for handle_location in annotation["handles_indexes"] ]

        # This does not actually work:
        # out_of_bounds = False
        # rotated_size = np.linalg.inv(im_orientation_mat) @ np.asarray(size)
        # print("rotated_size", rotated_size)
        # for h in handles_transformed:
        #     print(h)
        #     for i,k in enumerate(h):

        #         if ((rotated_size[i] > 0 and (k < 0 or k > rotated_size[i])) or
        #             (rotated_size[i] < 0 and (k > 0 or k < rotated_size[i]))):
        #                 out_of_bounds = True
        #                 print(rotated_size[i], k)
        # if out_of_bounds:
        #     averages.append([None] * len(acquisition_timepoints))
        #     continue

        for h in handles_transformed:
            if orientation in ("SAG", "COR"):
                h[2] = -h[2]
            for n,v in enumerate(h):
                if v < 0:
                    h[n] = h[n]-1
                h[n] = int(h[n]) 

        # print("transformed fixed", handles_transformed[0])
        slice_number = int(handles_transformed[0][idx])
        for h in range(len(handles_transformed)):
            handles_transformed[h] = handles_transformed[h][:idx]  + handles_transformed[h][idx+1:]
        # print(slice_number)
        if (key:=(orientation, slice_number)) in slice_cache:
            pixel_array = slice_cache[key]
        else:
            qs = dicom_set.instances.only("slice_location","instance_location","dicom_set__set_location").order_by('slice_location')
            if slice_number < 0:
                count = qs.all().count()
                slice_number = count + slice_number
            instance = qs[slice_number]

            file_location = Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location
            gz_location = file_location.with_suffix(file_location.suffix+".gz")
        
            if not file_location.exists() and gz_location.exists():
                with gzip.open(gz_location, 'r') as fp:
                    ds = pydicom.dcmread(fp)
            else:
                ds = pydicom.dcmread(file_location)
            pixel_array = ds.pixel_array
            slice_cache[(orientation, slice_number)] = ds.pixel_array
            
        if len(pixel_array.shape) == 2:
            pixel_array = pixel_array[np.newaxis,:,:]
        if annotation["tool"] == "EllipticalROI":
            [[_, top ], [_, bottom], [left, _], [right,_ ]] = handles_transformed

            # TODO: work out out-of-bounds properly
            if max(abs(left),abs(right)) > pixel_array.shape[2] or \
                 max(abs(top),abs(bottom)) > pixel_array.shape[1]:
                averages.append([None] * pixel_array.shape[0])
                continue
            # if min(top,bottom) < 0 or max(top,bottom) > pixel_array.shape[1] or \
            #     min(left, right) < 0 or max(left,right) > pixel_array.shape[2]:
            #     averages.append([None] * pixel_array.shape[0])
            #     continue

            # Pull out the rectangle described by the handles
            subarray = pixel_array[:,top:bottom,left:right]

            # Mask out an ellipse
            def masked(in_array):
                # Not an entirely accurate ellipse especially for small ones
                ry, rx = map(lambda x: (x-1)/2.0,in_array.shape[1:3])
                y,x = np.ogrid[-ry: ry+1, -rx: rx+1]
                mask = (x / rx)**2+(y / ry)**2 > 1 
                v = in_array.view(np.ma.MaskedArray)
                v.mask = mask
                return v
            # show_array(subarray[0])
            subarray = subarray.astype('float32')
            values = summary_method(masked(subarray), (1,2)).flatten()
        elif annotation["tool"] == "Probe":
            # handle = handles_absolute[0][1:]
            handle = handles_transformed[0]
            # print(handle)
            # TODO: actually detect being out of bounds
            if abs(handle[1]) > pixel_array.shape[1] or \
                 abs(handle[0]) > pixel_array.shape[2]:
                averages.append([None] * pixel_array.shape[0])
                continue
            
            try:
                values = pixel_array[:,handle[1], handle[0]]
                values = values.astype('float32')
            except:
                averages.append([None] * pixel_array.shape[0])
                continue
        else:
            print("Unknown tool", annotation["tool"])
            averages.append([None] * pixel_array.shape[0])
            continue

        adj_mode = chart_options.get('adjust',None)
        if adj_mode == "zeroed":
            values = values - values[0]
        elif adj_mode == "normalized":
            values = ( values - values.min() ) 
            values /= values.max()
        averages.append(values.tolist())

    # In case the CINEs are undersampled in time
    if averages and len(averages[0]) < len(acquisition_timepoints):
        acquisition_timepoints = acquisition_timepoints[::len(acquisition_timepoints) // len(averages[0])]
    
    averages.insert(0,acquisition_timepoints)
    return JsonResponse(dict(data=np.asarray(averages).T.tolist()))