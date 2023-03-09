import django_rq
from loguru import logger

from portal.models import Case, ProcessingJob
from common.constants import GravisNames, GravisFolderNames

from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.work_job import do_job
from portal.jobs import docker_utils
from portal.jobs.utils import report_failure, report_success

def create_sub_previews(job, connection, result, *args, **kwargs):

    logger.info(
        f"SUCCESS DOCKER job = {job}; result = {result}; connection = {connection}; args = {args}"
    )

    processing_job = ProcessingJob.objects.get(rq_id=job.id)   
    case = processing_job.case
    dicom_set_sub = case.dicom_sets.get(type="SUB")

    try:
        job = ProcessingJob(
            status="CREATED", 
            category="CINE", 
            dicom_set=dicom_set_sub,
            case = case,
            parameters={})
        job.save()
        result = django_rq.enqueue(
            do_job,
            args=(GeneratePreviewsJob,job.id),
            # job_timeout=60*60*4,
            on_success=report_success,
            on_failure=report_failure,
            ) 
        job.rq_id = result.id
        job.save()
    except Exception as e:
        case.status = Case.CaseStatus.ERROR
        case.save()
        logger.exception(
            f"Exception creating a new cine generation processing job for {dicom_set_sub.set_location} "
        )
    # TODO: Store in db

def run(case):
    incoming_dicom_set = case.dicom_sets.get(origin="Incoming")
    
    try:            
        mra_job = ProcessingJob(
            docker_image="gravis-processing",
            dicom_set=incoming_dicom_set,
            category="DICOMSet",
            case=case,
            status="Pending",
        )
        mra_job.save()
    except Exception as e:
        case.status = Case.CaseStatus.ERROR
        case.save()
        logger.exception(
            f"Exception creating a new processing job for {incoming_dicom_set.set_location} "
        )
        return

    try:
        main_processing_job = django_rq.enqueue(
            docker_utils.do_docker_job,
            mra_job.id,
            on_success=report_success,
            on_failure=report_failure,
        )
        mra_job.rq_id = main_processing_job.id
        mra_job.save()
    except Exception as e:
        docker_utils.process_job_error(mra_job.id, e)
        logger.exception(
            f"Exception enqueueing a new processing job for {incoming_dicom_set.set_location} "
        )
        return

    GeneratePreviewsJob.enqueue_work(case, depends_on=main_processing_job,parameters=dict(source_type="SUB",source_job=mra_job.id))
    GeneratePreviewsJob.enqueue_work(case, incoming_dicom_set, main_processing_job)
