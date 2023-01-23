import json
import math
import numpy as np
from loguru import logger
import pydicom
import os
from pathlib import Path
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

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


@login_required
def case_metadata(request, case, dicom_set, study=None):
    fields = ["series_uid","series_number", "slice_location", "acquisition_number", "acquisition_seconds"]

    q = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set=dicom_set)
    if study:
        q = q.filter(study_uid=study)
    series = q.values(*fields).order_by('series_uid').distinct('series_uid').all()

    
    result = [{
        f:k[f] for f in fields
    } for k in sorted(list(series),
        key=lambda x:(x.get('acquisition_number',0), x.get('series_number',0),x.get('slice_location',0)))
    ]
    return JsonResponse(result, safe=False)

@login_required
def timeseries_data(request, case, source_set):
    data = json.loads(request.body)

    # averages = np.zeros((120,1+len(data['annotations'])))
    # averages[:,0] = np.asarray(range(120))
    averages = []
    

    chart_options = data.get('chart_options',{})        
    mode = chart_options.get('mode','mean')
    summary_method = dict(mean=np.ma.mean,
                median=np.ma.median,
                ptp=np.ma.ptp)[mode]

    acquisition_seconds = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set=source_set).values("acquisition_seconds").distinct("acquisition_seconds")
    acquisition_timepoints = sorted(list((k['acquisition_seconds'] for k in acquisition_seconds)))
    ax_preview_set =  DICOMSet.objects.filter(processing_job__status="Success",case=case,type=f"CINE/AX",processing_job__dicom_set=source_set).latest('processing_job__created_at')

    ax_instances = ax_preview_set.instances
    example_instance = ax_instances.first()
    metadata = json.loads(example_instance.json_metadata)
    im_orientation_patient = np.asarray(metadata["00200037"]["Value"]).reshape((2,3))
    im_orientation_mat = np.rint(np.vstack((im_orientation_patient,[cross(*im_orientation_patient)])))

    size = [ int(metadata["00280011"]["Value"][0]), int(metadata["00280010"]["Value"][0]), ax_instances.count() ]

    # TODO: Calculate out-of-bounds properly. It's checked on the client, but still...
    for i, annotation in enumerate(data['annotations']):
        idx = np.abs(annotation['normal']).argmax()
        orientation = ['SAG','COR','AX'][idx]
        dicom_set = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=f"CINE/{orientation}",processing_job__dicom_set=source_set).latest('processing_job__created_at')
        instances = dicom_set.instances
        example_instance = instances.first()
        handles_transformed = [ (np.linalg.inv(im_orientation_mat) @ handle_location).tolist() for handle_location in annotation["handles_indexes"] ]


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
            if orientation == "COR":
                h[0] = -h[0]
            for n,v in enumerate(h):
                if v < 0:
                    h[n] = h[n]-1
                h[n] = int(h[n]) 


        # print("transformed fixed", handles_transformed[0])
        slice_number = int(handles_transformed[0][idx])
        for h in range(len(handles_transformed)):
            handles_transformed[h] = handles_transformed[h][:idx]  + handles_transformed[h][idx+1:]
        # print(slice_number)

        instance = list(instances.order_by('slice_location').all())[slice_number]
        ds = pydicom.dcmread( Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location )
        pixel_array = ds.pixel_array
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


@login_required
def processed_results_json(request, case, category, source_set):
    # fields = ["series_number", "slice_location", "acquisition_number"]
    case = Case.objects.get(id=int(case))
    # slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    job = ProcessingJob.objects.filter(status="Success", case=case, dicom_set=source_set, category=category).latest("created_at")
    return JsonResponse(dict(result = job.json_result))

@login_required
def preview_urls(request, case, source_set, view, location):
    case = Case.objects.get(id=int(case))
    dicom_set = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=f"CINE/{view}").filter(processing_job__dicom_set=source_set)

    location = np.asarray(list(map(int, location.split(","))))

    instances = dicom_set.latest('processing_job__created_at').instances.order_by("slice_location").all()
    im_orientation_patient = np.asarray(json.loads(instances[0].json_metadata)["00200037"]["Value"]).reshape((2,3))
    im_orientation_mat = np.rint(np.vstack((im_orientation_patient,[cross(*im_orientation_patient)])))

    # print(location)
    transformed_location = (np.linalg.inv(im_orientation_mat) @ location)
    # print(transformed_location)
    slice_number = int(transformed_location[ [ "SAG", "COR", "AX"].index(view) ])
    if slice_number < 0:
        slice_number -= 1
    instance = list(instances)[slice_number]

    location = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
    wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
    return JsonResponse(dict(urls=[ wado_uri +f"?frame={n}" for n in range(instance.num_frames)]))

@login_required
def processed_results_urls(request, case, case_type, source_set):
    fields = ["series_number", "slice_location", "acquisition_number"]
    case = Case.objects.get(id=int(case))
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_set = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=case_type, processing_job__dicom_set=source_set)
    instances = dicom_set.latest('processing_job__created_at').instances.filter(**slices_lookup).order_by("slice_location") # or "instance_number"


    urls = []
    for instance in instances:
        location = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
        wado_uri = "wadouri:"+str(Path(settings.MEDIA_URL) / location)
        if (instance.num_frames or 1) > 1:
            urls.extend( [ wado_uri +f"?frame={n}" for n in range(instance.num_frames)])
        else:
            urls.append(wado_uri)
    return JsonResponse(dict(urls=urls))

# @login_required
# def preview_data(request, case, view, index):
#     instance = DICOMInstance.objects.get(slice_location=index, dicom_set__case=case, dicom_set__type=f"CINE/{view.upper()}",dicom_set__processing_job__status="Success",dicom_set__processing_job__dicom_set__origin="Incoming")
#     loc = (Path(instance.dicom_set.set_location) / instance.instance_location).relative_to(settings.DATA_FOLDER)
#     result = ["wadouri:"+str(Path("/media") / loc) + f"?frame={n}" for n in range(instance.num_frames or 1)]
#     return JsonResponse(result, safe=False)
