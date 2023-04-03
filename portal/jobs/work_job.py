import json
from pathlib import Path
import stat

import django_rq
from django.http import HttpResponseNotFound, JsonResponse
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from loguru import logger
from portal.jobs.utils import send_failure_notification

def do_job(View,id):
    View._do_job(id)

def report_failure(job, connection, type, value, traceback):
    job = ProcessingJob.objects.get(id=job.args[1])
    job.status = "FAILED"
    job.error_description = str(value)
    logger.error(f"Job failure {job}")

    if job.case is not None and job.case.status == Case.CaseStatus.PROCESSING:
        job.case.status = Case.CaseStatus.ERROR
        job.case.save()
    job.save()
    send_failure_notification(job)

@method_decorator(login_required, name='dispatch')
class WorkJobView(View):
    type = "GENERIC"
    queue = "default"
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

        if dicom_set_id := json_in.get("dicom_set"):
            dicom_set = case.dicom_sets.get(id=dicom_set_id)
        else:
            dicom_set = case.dicom_sets.get(origin="Incoming")

        if not json_in.get("force",False):
            existing = ProcessingJob.successful.filter(dicom_set=dicom_set,
                    case = case,
                    parameters = json_in.get("parameters",{})).first()
            if existing:
                return JsonResponse(dict(id=existing.id))

        job = ProcessingJob(
            status="CREATED", 
            category=self.type, 
            dicom_set=case.dicom_sets.get(origin="Incoming"),
            case = case,
            parameters = json_in.get("parameters",{}))

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
        if job.dicom_set is None and "source_type" in job.parameters:
            job.dicom_set = DICOMSet.objects.get(type=job.parameters["source_type"], processing_job__id = job.parameters["source_job"])
        
        job_result =  cls.do_job(job)
        if type(job_result) in (list, tuple) and len(job_result) >= 2:
            job.json_result = job_result[0]
            dicom_sets = job_result[1]
        else:
            job.json_result = {}
            dicom_sets = []

        for f in (Path(job.case.case_location) / "processed").glob("*/"):
            if not f.is_dir():
                continue
            f.chmod(f.stat().st_mode | stat.S_IROTH | stat.S_IXOTH) # TODO: is this necessary?

        job.status = "SUCCESS"

        for d in dicom_sets:
            d.processing_job = job
            d.save()

        job.save()


    @classmethod
    def enqueue_work(cls, case, dicom_set=None, *, docker_image=None, depends_on=None, parameters={}):
        try:
            job = ProcessingJob(
                status = "CREATED",
                docker_image = docker_image,
                category = cls.type, 
                dicom_set = dicom_set,
                case = case,
                parameters = parameters)
            job.save()
            rq_result = django_rq.get_queue(cls.queue).enqueue(
                do_job,
                args = (cls,job.id),
                depends_on = depends_on,
                on_failure = report_failure,
                job_timeout = 60*60*4,
                # on_success=report_success,
                ) 
            job.rq_id = rq_result.id
            job.save()
            return job, rq_result
        except Exception as e:
            if case is not None:
                case.status = Case.CaseStatus.ERROR
                case.save()
                raise Exception(
                    f"Exception creating a new {cls.type} processing job for case {case}"
                )
            else:
                raise Exception(
                    f"Exception creating a new {cls.type} processing job with parameters{parameters}"
                )