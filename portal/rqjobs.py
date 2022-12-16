from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any
import uuid
from django.http import HttpResponseNotFound, JsonResponse
from django.shortcuts import render
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.urls import path
import numpy as np
import numpy.typing as npt
from pydicom import Dataset
import pydicom
from urllib3 import HTTPResponse
from datetime import datetime
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob

import django_rq

def do_job(View,id):
    View._do_job(id)

cross = (lambda x,y:np.cross(x,y))

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
        print(json_in["parameters"])

        case = Case.objects.get(id=json_in["case"])
        existing_q = ProcessingJob.objects.filter(dicom_set=case.dicom_sets.get(origin="Incoming"),
                case = case,
                parameters=json_in["parameters"],
                status = "Success")
        print(existing_q.query)
        existing = existing_q.first()
        if existing:
            print("Exists")
            return JsonResponse(dict(id=existing.id))
        print("Doesn't exist")
        job = ProcessingJob(
            status="CREATED", 
            category=self.type, 
            dicom_set=case.dicom_sets.get(origin="Incoming"),
            case = case,
            parameters=json_in["parameters"])

        job.save()
        django_rq.enqueue(do_job,args=(self.__class__,job.id),job_timeout=60*60*4)
        return JsonResponse(dict(id=job.id))

    @classmethod
    def do_job(cls, job: ProcessingJob):
        set = DICOMSet(case=job.case, processing_job = job)
        set.save()
        return ({}, [set])

    @classmethod
    def _do_job(cls,id):
        job = ProcessingJob.objects.get(id=id)
        json_result, dicom_sets = cls.do_job(job)
        job.json_result = json_result
        # job.result.save()

        for d in dicom_sets:
            d.processing_job = job
            d.save()

        job.status = "Success"
        job.save()


class CineJob(WorkJobView):
    type = "CINE"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        instances = job.dicom_set.instances.all()
        index = job.parameters["index"] # [ column, row, slice ] order
        normal = np.array([job.parameters["normal"]])
        viewUp = np.array([job.parameters["viewUp"]])
        viewHoriz = cross(normal,viewUp)
        # axis = np.argmax(np.abs(normal))

        # The index is in volume-space, but the normal is in world-space.
        # This tries to transform the normal into volume space...

        im_orientation_pt = np.asarray(json.loads(instances[0].json_metadata)["00200037"]["Value"]).reshape((2,3))
        # Eg 
        # array([[ 0.050593 ,  0.9987193,  0.       ],
        #        [-0.       , -0.       , -1.       ] ]

        im_orientation_mat = np.rint(np.vstack((im_orientation_pt,[cross(*im_orientation_pt)])))
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

        print("Axes", (normal_axis_number, rows_axis_number, cols_axis_number))
        # print(transformed_normal.T, transformed_viewUp.T, transformed_viewRight.T)


        series_uids = {k.series_uid for k in instances}

        split_by_series = [ sorted([k for k in instances if k.series_uid == uid],key = lambda x:x.slice_location,reverse=True) for uid in series_uids]
        # files_by_series = {uid: [ Path(i.dicom_set.set_location) / i.instance_location for i in by_series[uid]] for uid in series_uids}
        files_by_series = [ [ Path(i.dicom_set.set_location) / i.instance_location for i in k] for k in split_by_series ]
        # print(files_by_series)
        # array = None
        
        new_set = DICOMSet(set_location = Path(job.case.case_location) / "processed" / str(uuid.uuid4()),
            type = "CINE",
            case = job.case,
            processing_job = job)
        new_set.save()
        output_folder = Path(new_set.set_location)
        output_folder.mkdir()
        result = []

        new_study_uid = pydicom.uid.generate_uid()
        new_series_uid = pydicom.uid.generate_uid()
        for i, series in enumerate(files_by_series[::15]):
            print(f"{i} / {len(files_by_series)}")
            # v = DicomVolume(series)
            # pixel_array is in row-major order

            array = np.asarray([pydicom.dcmread(d).pixel_array for d in series]) 
            # array in [slice, row, column ] order
            array = array.transpose(2,1,0) 
            # array in [column, row, slice] order

            # The important transform: arrange the first axis to be the normal axis, and the remainder to be image rows, columns
            array = array.transpose(normal_axis_number, rows_axis_number, cols_axis_number)
            frame = array[index,:,:] # Cut out the slice we want
            if normal.sum() < 0: 
                # We're viewing from the "other" side, so the view needs to be flipped. By convention we flip horizontally
                frame = np.flip(frame,1)
            ds = pydicom.dcmread(series[0])
            ds.PixelData = frame.tobytes()
            ds.StudyInstanceUID = new_study_uid
            ds.SeriesInstanceUID = new_series_uid
            ds.SOPInstanceUID = pydicom.uid.generate_uid()
            ds.Rows = frame.shape[0]
            ds.Columns = frame.shape[1]
            min_ = np.min(frame) 
            max_ = np.max(frame)
            ds.WindowCenter = (max_+min_)/2
            ds.WindowWidth = (max_-min_)/2
            new_file = output_folder / f"frame.{i}.dcm"
            ds.save_as(new_file)
            
            new_instance = DICOMInstance.from_dataset(ds)
            new_instance.dicom_set = new_set
            new_instance.instance_location = str(new_file.relative_to(new_set.set_location))
            new_instance.save()

        
        return ({}, [new_set])
@dataclass
class VView:
    normal: npt.ArrayLike
    viewUp: npt.ArrayLike
    name: str
    viewHoriz: npt.ArrayLike = None
    transformed_axes: npt.ArrayLike = None
    dicom_set: DICOMSet = None


def generate_multiframe(cine):
    out_pixels = None
    out_ds = None
    dicoms = sorted(list(cine.glob("frame.*.dcm")), key=lambda x:int(x.name.split('.')[1]))
    # if (cine / "multiframe.dcm").exists():
    #     return
    for n, dcm in enumerate(dicoms):
        print(n,dcm)
        ds = pydicom.dcmread(dcm)
        if not out_ds:
            out_ds = ds
            out_ds.NumberOfFrames = len(dicoms)
            out_pixels = bytearray(b"\0"*(len(out_ds.PixelData) * out_ds.NumberOfFrames))
            frame_size = len(out_ds.PixelData)
        # out_pixels += ds.PixelData
        out_pixels[n*frame_size:(n+1)*frame_size] = ds.PixelData
    out_ds.PixelData = bytes(out_pixels)

    for dcm in dicoms:
        Path(dcm).unlink()

    return out_ds
class TestJob(WorkJobView):
    type = "CINE"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        num_frames = 0
        start_time = time.time() 

        instances = job.dicom_set.instances.all()
        im_orientation_pt = np.asarray(json.loads(instances[0].json_metadata)["00200037"]["Value"]).reshape((2,3))
        im_orientation_mat = np.rint(np.vstack((im_orientation_pt,[cross(*im_orientation_pt)])))

        ax_sagittal = [ 1, 0,  0 ]
        ax_coronal =  [ 0, 1,  0 ]
        ax_axial =    [ 0, 0, -1 ]
        viewUp_sagittal = [ 0,  0, 1 ]
        viewUp_coronal =  [ 0,  0, 1 ]
        viewUp_axial =    [ 0, -1, 0 ]

        views = [VView(*x) for x in [[ ax_sagittal, viewUp_sagittal, "SAG" ],
                                     [ ax_coronal,  viewUp_coronal,  "COR" ],
                                     [ ax_axial,    viewUp_axial,    "AX"  ]
                                     ]]
        # axis_numbers = []
        for v in views:
            print(v)
            v.viewHoriz         = cross(v.normal,v.viewUp)
            transformed_normal  = im_orientation_mat @ v.normal
            normal_axis_number  = np.abs(transformed_normal).argmax()
            transformed_viewUp  = im_orientation_mat @ v.viewUp
            rows_axis_number    = np.abs(transformed_viewUp).argmax()
            transformed_viewHoriz = im_orientation_mat @ v.viewHoriz
            cols_axis_number    = np.abs(transformed_viewHoriz).argmax()
            v.transformed_axes  = np.array([normal_axis_number, rows_axis_number, cols_axis_number])

            print(f"---{v.name}---")
            print("Normal",     v.normal,       transformed_normal.T,       normal_axis_number)
            print("Rows axis",  v.viewUp,       transformed_viewUp.T,       rows_axis_number)
            print("Cols axis",  v.viewHoriz,    transformed_viewHoriz.T,    cols_axis_number)
            print(v.transformed_axes)

        series_uids = {k.series_uid for k in instances}
        split_by_series = [ sorted([k for k in instances if k.series_uid == uid],key = lambda x:x.slice_location,reverse=True) for uid in series_uids]
        files_by_series = [ [ Path(i.dicom_set.set_location) / i.instance_location for i in k] for k in sorted(split_by_series,key=lambda x:x[0].acquisition_seconds) ]
        
        random_name = str(uuid.uuid4())
        for v in views:
            location = Path(job.case.case_location) / "processed" / (v.name+"-"+random_name)
            location.mkdir()
            v.dicom_set = DICOMSet(set_location = location,
                type = f"CINE/{v.name}",
                case = job.case,
                processing_job = job)
            v.dicom_set.save()
            # output_folder = Path(new_set.set_location)

        volume = None
        prototype_ds = None
        for i, files in enumerate(files_by_series):
            for j, file in enumerate(files):
                dcm = pydicom.dcmread(file)
                array = dcm.pixel_array # [ row, column ] order
                if volume is None:
                    volume = np.empty_like(array,shape=(len(files_by_series), *array.shape[::-1], len(files)))
                    # [ time, column, row, slice ] order
                    prototype_ds = dcm
                    print(volume.shape)
                volume[i,:,:,j] = array.T
        assert volume is not None

        for v in views:
            new_study_uid = pydicom.uid.generate_uid()
            new_series_uid = pydicom.uid.generate_uid()

            t_array = volume.transpose(*(0,*[1+x for x in v.transformed_axes]))
            # t_array is now in [ time, normal, rows, columns]
            if sum(v.normal) < 0: 
                # We're viewing from the "other" side, so the view needs to be flipped. By convention we flip horizontally
                t_array = np.flip(t_array,3)
            for i in range(t_array.shape[1]):
                ds = prototype_ds.copy()
                ds.NumberOfFrames   = t_array.shape[0]
                ds.Rows             = t_array.shape[2]
                ds.Columns          = t_array.shape[3]
                ds.PixelData        = t_array[:,i,:,:].tobytes()
                ds.SliceLocation    = str(i)+".0"
                ds.SeriesNumber     = str(i)

                ds.StudyInstanceUID  = new_study_uid
                ds.SeriesInstanceUID = new_series_uid
                ds.SOPInstanceUID    = pydicom.uid.generate_uid()

                ds.save_as(Path(v.dicom_set.set_location) / f"multiframe.{i}.dcm")
                print(Path(v.dicom_set.set_location) / f"multiframe.{i}.dcm")
                new_instance = DICOMInstance.from_dataset(ds)
                new_instance.dicom_set = v.dicom_set
                new_instance.instance_location = f"multiframe.{i}.dcm"
                new_instance.save()

        return (
            {"views": {v.name: dict(name=v.name,axes=v.transformed_axes.tolist()) for v in views}},
            [v.dicom_set for v in views]
        )
        # num_slices = len(files_by_series[0])
        # ds = pydicom.dcmread(files_by_series[0][0])
        # num_rows = int(ds.Rows)
        # num_cols = int(ds.Cols)

urls = [
    path("job/cine", CineJob.as_view()),
    path("job/test", TestJob.as_view())
]
