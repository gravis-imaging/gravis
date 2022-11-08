import json
from pathlib import Path
import uuid
from dcmannotate import DicomVolume
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import path
import numpy as np
from pydicom import Dataset
import pydicom
from urllib3 import HTTPResponse
from datetime import datetime
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob

import django_rq

def do_job(View,id):
    View._do_job(id)


@method_decorator(login_required, name='dispatch')
class WorkJobView(View):
    type="GENERIC"

    def get(self, request, *args, **kwargs):
        try:
            job = ProcessingJob.objects.get(id=request.GET["id"])
        except ProcessingJob.DoesNotExist:
            return HttpResponseNotFound()
        result = dict(id=job.id, category=job.category, status=job.status, parameters = job.parameters )

        result["json_result"] = job.json_result
        if sets := job.result_sets.all():
            dicom_sets = []
            for set in sets:
                dicom_sets.append([])
                instances = list(set.instances.all())
                # sort by acquisition number
                instances.sort(key=lambda x: int(json.loads(x.json_metadata)["00200012"]["Value"][0]))
                for instance in instances:
                    dicom_sets[-1].append(dict(study_uid=instance.study_uid, series_uid=instance.series_uid, instance_uid=instance.instance_uid))
            result["dicom_sets"] = dicom_sets
        # job.result.dicom_set.instances()
        return JsonResponse(result)


    def post(self, request, *args, **kwargs):
        json_in = json.loads(request.body)

        case = Case.objects.get(id=json_in["case"])
        job = ProcessingJob(
            status="CREATED", 
            category=self.type, 
            dicom_set=case.dicom_sets.get(type="Incoming"),
            case = case,
            parameters=json_in["parameters"])
        job.save()
        django_rq.enqueue(do_job,self.__class__,job.id)
        return JsonResponse(dict(id=job.id))

    @classmethod
    def do_job(cls, job: ProcessingJob):
        set = DICOMSet(case=job.case, processing_result = job)
        set.save()
        return ({}, set)

    @classmethod
    def _do_job(cls,id):
        job = ProcessingJob.objects.get(id=id)
        json_result, dicom_set = cls.do_job(job)
        job.json_result = json_result
        # job.result.save()

        if dicom_set:
            dicom_set.processing_result = job
            dicom_set.save()

        job.status = "SUCCESS"
        job.save()


class CineJob(WorkJobView):
    type = "CINE"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        instances = job.dicom_set.instances.all()
        index = job.parameters["index"] # [ column, row, slice ] order
        normal = np.array([job.parameters["normal"]])
        viewUp = np.array([job.parameters["viewUp"]])
        viewHoriz = np.cross(normal,viewUp)
        # axis = np.argmax(np.abs(normal))

        # The index is in volume-space, but the normal is in world-space.
        # This tries to transform the normal into volume space...

        im_orientation_pt = np.asarray(json.loads(instances[0].json_metadata)["00200037"]["Value"]).reshape((2,3))
        # Eg 
        # array([[ 0.050593 ,  0.9987193,  0.       ],
        #        [-0.       , -0.       , -1.       ] ]

        im_orientation_mat = np.rint(np.vstack((im_orientation_pt,[np.cross(*im_orientation_pt)])))
        # Eg 
        # M = [  0,  1,  0 ],
        #     [ -0, -0, -1 ],
        #     [ -1, -0,  0 ]]

        transformed_normal = im_orientation_mat @ normal.T
        # Eg an axial view:
        #                  T            T
        #    M * [ 0 0 -1 ]  = [ 0 1 0 ]
        
        normal_axis_number = np.abs(transformed_normal).argmax()
        # argmax([ 0 1 0 ]) = 1, the normal points along the columns axis

        index = index[normal_axis_number]
        # eg 43, we're getting the 43rd slab along the column axis

        # Do this for the in-plane axes as well
        transformed_viewUp = im_orientation_mat @ viewUp.T
        rows_axis_number = np.abs(transformed_viewUp).argmax()
        transformed_viewHoriz = im_orientation_mat @ viewHoriz.T
        cols_axis_number = np.abs(transformed_viewHoriz).argmax()

        
        print("Normal",normal, transformed_normal.T, normal_axis_number, index)

        print("Rows axis", viewUp, transformed_viewUp.T, rows_axis_number)
        print("Cols axis", viewHoriz, transformed_viewHoriz.T, cols_axis_number)

        # print(transformed_normal.T, transformed_viewUp.T, transformed_viewRight.T)


        series_uids = {k.series_uid for k in instances}

        split_by_series = [ [k for k in instances if k.series_uid == uid] for uid in series_uids]
        # files_by_series = {uid: [ Path(i.dicom_set.set_location) / i.instance_location for i in by_series[uid]] for uid in series_uids}
        files_by_series = [ [ Path(i.dicom_set.set_location) / i.instance_location for i in k] for k in split_by_series ]
        # print(files_by_series)
        # array = None
        
        new_set = DICOMSet(set_location = Path(job.case.case_location) / "processed" / str(uuid.uuid4()),
            type = "CINE",
            case = job.case,
            processing_result = job)
        new_set.save()
        output_folder = Path(new_set.set_location)
        output_folder.mkdir()
        result = []

        new_study_uid = pydicom.uid.generate_uid()
        new_series_uid = pydicom.uid.generate_uid()
        for i, series in enumerate(files_by_series[::]):
            v = DicomVolume(series)
            # pixel_array is in row-major order
            array = np.asarray([d.pixel_array for d in v]) 
            # array in [slice, row, column ] order
            array = array.transpose(2,1,0) 
            # array in [column, row, slice] order

            # The important transform: arrange the first axis to be the normal axis, and the remainder to be image rows, columns
            array = array.transpose(normal_axis_number, rows_axis_number, cols_axis_number)
            frame = array[index,:,:] # Cut out the slice we want
            if normal.sum() < 0: 
                # We're viewing from the "other" side, so the view needs to be flipped. By convention we flip horizontally
                frame = np.flip(frame,1)
            ds = v[0].copy()
            ds.PixelData = frame.tobytes()
            ds.StudyInstanceUID = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID = pydicom.uid.generate_uid()
            ds.Rows = frame.shape[0]
            ds.Columns = frame.shape[1]
            new_file = output_folder / f"frame.{i}.dcm"
            ds.save_as(new_file)
            
            new_instance = DICOMInstance.from_dataset(ds)
            new_instance.dicom_set = new_set
            new_instance.instance_location = str(new_file.relative_to(new_set.set_location))
            new_instance.save()

        
        return ({}, new_set)

urls = [
    path("job/cine", CineJob.as_view())
]