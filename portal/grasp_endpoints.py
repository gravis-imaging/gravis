import json
import math
import numpy
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
    
    # averages = numpy.zeros((120,1+len(data['annotations'])))
    # averages[:,0] = numpy.asarray(range(120))
    averages = []
    

    chart_options = data.get('chart_options',{})        
    mode = chart_options.get('mode','mean')
    summary_method = dict(mean=numpy.ma.mean,
                median=numpy.ma.median,
                ptp=numpy.ma.ptp)[mode]

    acquisition_seconds = DICOMInstance.objects.filter(dicom_set__case=case, dicom_set=source_set).values("acquisition_seconds").distinct("acquisition_seconds")
    averages.append(sorted(list((k['acquisition_seconds'] for k in acquisition_seconds))))
    # case = Case.objects.get(id=int(case))
    for i, annotation in enumerate(data['annotations']):
        idx = numpy.abs(annotation['normal']).argmax()
        orientation = ['SAG','COR','AX'][idx]
        instances = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=f"CINE/{orientation}").latest('processing_job__created_at').instances
        example_instance = instances.first()
        # logger.info(annotation["ellipse"])
        normal = numpy.asarray(annotation["normal"])
        viewUp = numpy.asarray(annotation["view_up"])
        viewLeft = (lambda x,y:numpy.cross(x,y))(normal,viewUp) # workaround for numpy bug that makes Pylance think the rest of the code is unreachable
        # logger.info(f"up {viewUp:}")
        # logger.info(f"left {viewLeft:}")

        flipX = False
        flipY = False
        if sum(viewUp) > 0:
            flipY = True
        if sum(viewLeft) > 0:
            flipX = True        
        # logger.info(f"flip X: {flipX}  Y:{flipY}")
        handles = numpy.asarray(annotation["handles"])
        bounds = numpy.asarray(annotation["bounds"])
        tool = numpy.asarray(annotation["tool"])
        bounds = bounds.reshape(3,2) # reshape into three min/max pairs

        # logger.info(f"viewUp {annotation['view_up']}"),
        
        # logger.info(f"bounds {bounds}"),
        dims_size = bounds[:,1] - bounds[:,0]
        # normalize coordinates to between 0 and 1
        handles_relative = (handles[:,:] - bounds[:,0]) / dims_size
        # 
        slice_number = round(handles_relative[0][idx] * instances.count() - 0.5)
        handles_relative = numpy.delete(handles_relative,idx,1)
        if flipX:
            handles_relative[:,0] = 1.0 - handles_relative[:,0]
        if flipY:
            handles_relative[:,1] = 1.0 - handles_relative[:,1]

        instance = instances.filter(slice_location=slice_number).get()
        ds = pydicom.dcmread( Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location )
        
        # Calculate pixel locations of handles
        handles_absolute = numpy.rint(handles_relative[:,:] * [ds.Columns, ds.Rows] - 0.5).astype(int)
        [[_, top], [_, bottom], [left,_], [right,_ ]] = handles_absolute

        top, bottom = sorted([top, bottom])
        left, right = sorted([right, left])
        print(f"t {top} b {bottom} r {right} l {left}")
        center = numpy.rint((handles_absolute[0] + handles_absolute[1])/2.0)
        # logger.info(f"{handles_absolute[0] } + {handles_absolute[1] } = center {center}, {idx}")
              
        # logger.info(f"handles_absolute {handles_absolute}")
        # logger.info(f"top {top} bottom {bottom} left {left} right {right}")
        # logger.info(f"center {center}")
        # # avgs = numpy.mean(subarray, (1,2)).flatten()

        
        if min(top,bottom) < 0 or max(top,bottom) > ds.pixel_array.shape[1] or \
            min(left, right) < 0 or max(left,right) > ds.pixel_array.shape[2]:
            averages.append([None] * ds.pixel_array.shape[0])
            continue

        if tool == "GravisROI":
            # Pull out the rectangle described by the handles
            subarray = ds.pixel_array[:,top:bottom,left:right]

            def masked(in_array):
                # Not an entirely accurate ellipse especially for small ones
                ry, rx = map(lambda x: (x-1)/2.0,in_array.shape[1:3])
                y,x = numpy.ogrid[-ry: ry+1, -rx: rx+1]
                mask = (x / rx)**2+(y / ry)**2 > 1 
                v = in_array.view(numpy.ma.MaskedArray)
                v.mask = mask
                return v

            subarray = subarray.astype('float32')
            values = summary_method(masked(subarray), (1,2)).flatten()
        elif tool == "Probe":
            values = ds.pixel_array[:,handles_absolute[0][1], handles_absolute[0][0]]
            values = values.astype('float32')
        else:
            averages.append([None] * ds.pixel_array.shape[0])
            continue
        adj_mode = chart_options.get('adjust',None)
        if adj_mode == "zeroed":
            values = values - values[0]
        elif adj_mode == "normalized":
            values = ( values - values.min() ) 
            values /= values.max()
        averages.append(values.tolist())

    return JsonResponse(dict(data=numpy.asarray(averages).T.tolist()))

@login_required
def processed_results_urls(request, case, case_type, source_set=None):
    fields = ["series_number", "slice_location", "acquisition_number"]
    case = Case.objects.get(id=int(case))
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_set = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=case_type)
    if source_set:
        dicom_set = dicom_set.filter(processing_job__dicom_set=source_set)
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
