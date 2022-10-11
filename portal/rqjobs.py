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
from urllib3 import HTTPResponse

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
                for instance in set.instances.all():
                    dicom_sets[-1].append(instance.json_metadata)
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

class TestWork(WorkJobView):
    type = "TEST"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        params = job.parameters
        axis = 0
        index = 70
        instances = job.dicom_set.instances.all()
        series_uids = {k.series_uid for k in instances}

        by_series = {uid: [k for k in instances if k.series_uid == uid] for uid in series_uids}
        
        files_by_series = {uid: [ Path(i.dicom_set.set_location) / i.instance_location for i in by_series[uid]] for uid in series_uids}
        # print(files_by_series)
        # array = None

        new_set = DICOMSet(set_location = Path(job.case.case_location) / str(uuid.uuid4()),
            type = "CINE",
            case = job.case,
            processing_result = job)
        new_set.save()
        
        result = []
        for k in files_by_series:
            v = DicomVolume(files_by_series[k])
            n=0
            array = np.asarray([d.pixel_array for d in v])
            array = array.transpose(1,2,0)
            frame = array.take(index,axis=axis)


            job.case.case_location



        return ({"result":1234}, None)

urls = [
    path("job/test", TestWork.as_view())
]