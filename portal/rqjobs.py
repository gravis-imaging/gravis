import dataclasses
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

def cross(*c) -> npt.ArrayLike:
    return np.cross(*c)

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


@dataclasses.dataclass
class VView:
    name: str
    normal: npt.ArrayLike
    viewUp: npt.ArrayLike
    viewHoriz: npt.ArrayLike = None
    transformed_axes: npt.ArrayLike = None
    flip_for_preview: list = dataclasses.field(default_factory=list)
    flip_for_timeseries: list = dataclasses.field(default_factory=list)
    dicom_set: DICOMSet = None

    transformed_normal : npt.ArrayLike = None
    transformed_viewUp : npt.ArrayLike = None
    transformed_viewHoriz : npt.ArrayLike = None

    def to_dict(self):
        return dict(
            name = self.name,
            normal = self.normal,
            viewUp = self.viewUp,
            viewHoriz = self.viewHoriz.tolist() if self.viewHoriz is not None else None,
            transformed_axes = self.transformed_axes.tolist() if self.transformed_axes is not None else None,
            flip_for_preview = self.flip_for_preview,
            flip_for_timeseries = self.flip_for_timeseries,
            transformed_normal = self.transformed_normal.tolist() if self.transformed_normal is not None else None,
            transformed_viewUp = self.transformed_viewUp.tolist() if self.transformed_viewUp is not None else None,
            transformed_viewHoriz = self.transformed_viewHoriz.tolist() if self.transformed_viewHoriz is not None else None,
        )
class TestJob(WorkJobView):
    type = "CINE"

    @classmethod
    def calc_views_for_set(cls, im_orientation_pt):
        im_orientation_mat = np.rint(np.vstack((im_orientation_pt,[cross(*im_orientation_pt)])))
        print(im_orientation_mat)
        normal_sagittal = [ 1, 0,  0 ]
        normal_coronal =  [ 0, 1,  0 ]
        normal_axial =    [ 0, 0, -1 ]
        viewUp_sagittal = [ 0,  0, 1 ]
        viewUp_coronal =  [ 0,  0, 1 ]
        viewUp_axial =    [ 0, -1, 0 ]

        views = [VView(*x) for x in [[ "SAG", normal_sagittal, viewUp_sagittal ],
                                     [ "COR", normal_coronal,  viewUp_coronal  ],
                                     [ "AX",  normal_axial,    viewUp_axial    ]]
                ]
        for v in views:
            v.viewHoriz         = cross(v.normal,v.viewUp)
            v.transformed_normal  = im_orientation_mat @ v.normal
            normal_axis_number  = np.abs(v.transformed_normal).argmax()
            v.transformed_viewUp  = im_orientation_mat @ v.viewUp
            rows_axis_number    = np.abs(v.transformed_viewUp).argmax()
            v.transformed_viewHoriz = im_orientation_mat @ v.viewHoriz
            cols_axis_number    = np.abs(v.transformed_viewHoriz).argmax()
            v.transformed_axes  = np.array([normal_axis_number, rows_axis_number, cols_axis_number])

            print(f"---{v.name}---")
            print("Normal",     v.normal,       v.transformed_normal.T,       normal_axis_number)
            print("Rows axis",  v.viewUp,       v.transformed_viewUp.T,       rows_axis_number)
            print("Cols axis",  v.viewHoriz,    v.transformed_viewHoriz.T,    cols_axis_number)
            print(v)

            # Hardcoding these for now. 
            # --- SAGITTAL
            if np.array_equal(im_orientation_mat, 
                    np.array(
                        [[ 0.,  1.,  0.],
                         [-0., -0., -1.],
                         [-1.,  0.,  0.]])):
                if v.name in ("COR", "SAG"):
                    v.flip_for_preview.append(3)
                elif v.name == "AX":
                    v.flip_for_timeseries.append(2)
            # --- AXIAL
            elif np.array_equal(im_orientation_mat, 
                    np.array(
                        [[ 1., -0., -0.],
                         [ 0.,  1., -0.],
                         [ 0.,  0.,  1.]])):
                if v.name in ("COR", "SAG"):
                    v.flip_for_preview.append(3)
                    v.flip_for_timeseries.append(1)
                if v.name == "COR":
                    v.flip_for_preview.append(1)
                    v.flip_for_timeseries.append(2)
        return views

    @classmethod
    def do_job(cls, job: ProcessingJob):
        instances = job.dicom_set.instances.all()
        im_orientation_patient = np.asarray(json.loads(instances[0].json_metadata)["00200037"]["Value"]).reshape((2,3))
        views = cls.calc_views_for_set(im_orientation_patient)

        series_uids = { k.series_uid for k in instances }
        split_by_series = [ sorted([k for k in instances if k.series_uid == uid], key = lambda x:x.slice_location) for uid in series_uids ]
        files_by_series = [ [ Path(i.dicom_set.set_location) / i.instance_location for i in k] for k in sorted(split_by_series,key=lambda x:x[0].acquisition_seconds) ]
        
        random_name = str(uuid.uuid4())
        for v in views:
            location = Path(job.case.case_location) / "processed" / (v.name+"-"+random_name)
            location.mkdir()
            v.dicom_set = DICOMSet(
                set_location = location,
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

        # raise Exception("foo")
#         print(f"""P2
# {volume.shape[2]/2} {volume.shape[1]/2}
# {volume[0].max()}
# """+"\n".join(" ".join([str(k) for k in r]) for r in volume[0,::2,::2,100].T))
        for v in views:
            new_study_uid = pydicom.uid.generate_uid()
            new_series_uid = pydicom.uid.generate_uid()
            
            t_array = volume[:]
            for k in v.flip_for_preview:
                t_array = np.flip(t_array,k)
            t_array = t_array.transpose(*(0,*[1+x for x in v.transformed_axes]))
            # t_array is now in [ time, normal, rows, columns ]

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
                new_instance = DICOMInstance.from_dataset(ds)
                new_instance.dicom_set = v.dicom_set
                new_instance.instance_location = f"multiframe.{i}.dcm"
                new_instance.save()

        return (
            {"views": {v.name: v.to_dict() for v in views}},
            [v.dicom_set for v in views]
        )

urls = [
    # path("job/cine", CineJob.as_view()),
    path("job/test", TestJob.as_view())
]
