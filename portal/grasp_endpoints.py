import json
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
def timeseries_data(request, case, source_set=None):
    data = json.loads(request.body)
    
    # averages = numpy.zeros((120,1+len(data['annotations'])))
    # averages[:,0] = numpy.asarray(range(120))
    averages = []
    averages.append(list(range(120)))
    # case = Case.objects.get(id=int(case))
    for i, annotation in enumerate(data['annotations']):
        idx = numpy.abs(annotation['normal']).argmax()
        orientation = ['SAG','COR','AX'][idx]
        instances = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=f"CINE/{orientation}").latest('processing_job__created_at').instances
        example_instance = instances.first()
        # logger.info(annotation["ellipse"])
        normal = numpy.asarray(annotation["normal"])
        viewUp = numpy.asarray(annotation["view_up"])
        viewLeft = numpy.cross(normal,viewUp)
        # logger.info(f"normal {normal:}")
        logger.info(f"up {viewUp:}")
        logger.info(f"left {viewLeft:}")

        flipX = False
        flipY = False
        if sum(viewUp) > 0:
            flipY = True
        if sum(viewLeft) > 0:
            flipX = True        
        logger.info(f"flip X: {flipX}  Y:{flipY}")
        handles = numpy.asarray(annotation["ellipse"])
        bounds = numpy.asarray(annotation["bounds"])
        bounds = bounds.reshape(3,2)
        # logger.info(f"viewUp {annotation['view_up']}"),
        
        logger.info(f"bounds {bounds}"),
        # bounds_shifted = bounds[:,:] - bounds[:,0][:,None]
        dims_size = bounds[:,1] - bounds[:,0]
        
        handles_relative = (handles[:,:] - bounds[:,0]) / dims_size
        # logger.info(f"handles_relative: {handles_relative}")
        logger.info(f"handles_relative: {handles_relative}")

        # logger.info(f"dims_size {dims_size}"),
        # logger.info(f"handles {handles}")
        slice_number = round(handles_relative[0][idx] * instances.count() - 0.5)
        handles_relative = numpy.delete(handles_relative,idx,1)
        if flipX:
            handles_relative[:,0] = 1.0 - handles_relative[:,0]
        if flipY:
            handles_relative[:,1] = 1.0 - handles_relative[:,1]

        instance = instances.filter(slice_location=slice_number).get()
        ds = pydicom.dcmread( Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location )
        
        handles_absolute = numpy.rint(handles_relative[:,:] * [ds.Columns, ds.Rows] - 0.5)
        # logger.info(f"handles_abs {handles_absolute}")
        center = numpy.rint((handles_absolute[0] + handles_absolute[1])/2)
        # logger.info(f"{handles_absolute[0] } + {handles_absolute[1] } = center {center}, {idx}")

        # center = numpy.delete(center,idx)
        # center_2 = numpy.zeros(center.shape)
        # center[:] = center[:] - bounds[:,0]
        
        logger.info(f"center {center}")
        subarray = ds.pixel_array[:,int(center[1]),int(center[0])]
        # avgs = numpy.mean(subarray, (1,2)).flatten()
        averages.append(subarray.tolist())
        # center_px = numpy.delete(center,idx)
        # logger.info(f"center_px {center_px.round()}")
        # logger.info(f"Orientation: {orientation}")
        # logger.info(handles)
        # # A really silly way to work out what the slice location is.
        # slice_index = numpy.abs(numpy.diff(annotation["ellipse"],n=3,axis=0)).argmin()
        # slice_location = annotation["ellipse"][0][slice_index]
        # logger.info(numpy.asarray(annotation["ellipse"]))
        # extent = numpy.delete(numpy.asarray(annotation["ellipse"]), slice_index,axis=1)

        # logger.info(slice_location)
        # logger.info(extent)

        # top = extent[0,0]
        # bottom = extent[1,0]
        # left = extent[2,1]
        # right = extent[3,1]
        # logger.info(", ".join(map(str,[top,bottom,left,right])))
        # instance = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=f"CINE/{orientation}").latest('processing_job__created_at').instances.filter(slice_location=slice_location).get()
        # ds = pydicom.dcmread( Path(settings.DATA_FOLDER) / instance.dicom_set.set_location / instance.instance_location )
        # subarray = ds.pixel_array[:,top:bottom,min(left,right):max(left,right)]
        # avgs = numpy.mean(subarray, (1,2)).flatten()
        # averages.append(avgs.tolist())
        # print(avgs)
    # logger.info(numpy.asarray(averages))
    # logger.info(data)
    # def gen_data(x):
    #     return (x,) +( random.random(),) * len(data['annotations'])


    return JsonResponse(dict(data=numpy.asarray(averages).T.tolist()))

@login_required
def processed_results_urls(request, case, case_type, source_set=None):
    fields = ["series_number", "slice_location", "acquisition_number"]
    case = Case.objects.get(id=int(case))
    slices_lookup = {k: request.GET.get(k) for k in fields if k in request.GET}
    dicom_set = DICOMSet.objects.filter(processing_job__status="Success",case=case,type=case_type)
    if source_set:
        dicom_set = dicom_set.filter(processing_job__dicom_set=source_set)
    instances = dicom_set.latest('processing_job__created_at').instances.filter(**slices_lookup)

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
