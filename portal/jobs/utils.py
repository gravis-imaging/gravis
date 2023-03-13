import django_rq
from loguru import logger

from portal.models import Case, ProcessingJob

def report_success(job, connection, result, *args, **kwargs):
    logger.info(
        f"SUCCESS job = {job}; result = {result}; connection = {connection}; args = {args}"
    )
    # TODO: Store in db


def report_failure(job, connection, type, value, traceback):
    logger.info(
        f"FAILURE job = {job}; traceback = {traceback}; type = {type}; value = {value}"
    )
    # TODO: Store in db

def start_processing_job(function, category, case=None, dicom_set=None, *, args, docker_image):

    # create a job for copying file from incoming to input folder:
    try:
        new_job = ProcessingJob(
            category = category,
            parameters = dict(args=args),
            case = case,
            dicom_set = dicom_set, 
            docker_image = docker_image,
            status = "Pending",
        )
        new_job.save()
    except Exception as e:
        raise Exception(f"Failed creating a new {category} job for {args}")

    try:
        result = django_rq.enqueue(
            function,
            new_job.id,
            args=args,
            on_success=report_success,
            on_failure=report_failure,
        )
        new_job.rq_id = result.id
        new_job.save()
    except Exception as e:
        new_job.error_description = e
        new_job.save()
        # process_job_error(new_job.id, e)
        raise Exception(f"Failed enqueueing a new {category} job for {args}")
    return result