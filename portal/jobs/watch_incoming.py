# import logging
from unittest.mock import NonCallableMagicMock
from loguru import logger
from pathlib import Path
import shutil
from time import sleep
import os, json
from typing import Tuple
from uuid import uuid4

from django.conf import settings
import django_rq

import portal.jobs.dicom_set_utils as dicom_set_utils
import portal.jobs.docker_utils as docker_utils
from portal.models import Case, ProcessingJob
from common.constants import GravisNames, GravisFolderNames
from .cine_generation import GeneratePreviewsJob
from .work_job import do_job
import common.helper as helper

# logging.basicConfig(filename='watch_incoming.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)


def load_json(incoming_case, new_folder, error_folder) -> Tuple[bool, Case]:
    json_name = "study.json"
    incoming_json_file = Path(incoming_case / json_name)
    try:
        if incoming_json_file.exists():
            with open(incoming_json_file, "r") as myfile:
                d = myfile.read()
            payload = json.loads(d)
        else:
            payload = {}
    except Exception:
        logger.exception(f"Unable to read {json_name} in {incoming_case}.")
        payload = {}

    try:
        case_status = Case.CaseStatus.PROCESSING
        case_location = str(new_folder)
        new_case = Case(
            patient_name=payload.get("patient_name", ""),
            mrn=payload.get("mrn", ""),
            acc=payload.get("acc", ""),
            case_type=payload.get("case_type", ""),
            exam_time=payload.get("exam_time", "1900-01-01 00:00"),
            receive_time=payload.get("receive_time", "1900-01-01 00:00"),
            twix_id=payload.get("twix_id", ""),
            num_spokes=payload.get("num_spokes", ""),
            case_location=case_location,
            settings=payload.get("settings", ""),
            incoming_payload=payload,
            status=case_status,
        )  # Case(data_location="./data/cases)[UID]")
        new_case.save()
        study_keys = ["patient_name", "mrn", "acc", "case_type", "exam_time", "twix_id", "num_spokes"]
        # TODO check that values for these fields are valid. If not set status to ERROR/.
        for key in study_keys:
            if key not in payload:
                logger.exception(f"Field {key} is missing from study.json file.")
                return False, new_case
    except Exception as e:
        logger.exception(f"Cannot create case for {error_folder}. Exception: {e}")
        return False, None
    return True, new_case


def process_error_folder(
    case: Case, incoming_folder: Path, error_folder: Path, lock: Path
):

    dicom_set_utils.move_files(incoming_folder, error_folder)
    if not case is None:
        case.status = Case.CaseStatus.ERROR
        case.case_location = str(error_folder)
        case.save()
    try:
        lock.free()
        # os.unlink(complete_file_path)
        os.rmdir(incoming_folder)
        # os.rmdir(error_folder)
    except Exception as e:
        logger.exception(
            f"Exception {e} during cleaning stage after moving {incoming_folder} to the {error_folder} folder."
        )
    logger.error(f"Done Processing {incoming_folder} with error.")


def process_folder(job_id: int, incoming_case: Path):

    try:
        job: ProcessingJob = ProcessingJob.objects.get(id=job_id)
    except Exception as e:
        logger.exception(f"ProcessingJob with id {job_id} does not exist.")
        return False

    # Move from incoming to cases
    logger.info(f"Processing {incoming_case}")

    cases = Path(settings.CASES_FOLDER)
    dest_folder_name = helper.generate_folder_name()
    new_folder = cases / dest_folder_name
    error_folder = Path(settings.ERROR_FOLDER) / dest_folder_name
    input_dest_folder = new_folder / GravisFolderNames.INPUT
    processed_dest_folder = new_folder / GravisFolderNames.PROCESSED
    findings_dest_folder = new_folder / GravisFolderNames.FINDINGS
    # complete_file_path = Path(incoming_case) / GravisNames.COMPLETE
    lock_file_path = Path(incoming_case) / GravisNames.LOCK
    if lock_file_path.exists():
        # Series is locked, so another instance might be working on it
        return True

    # Create lock file in the incoming folder and prevent other instances from working on this series
    try:
        lock = helper.FileLock(lock_file_path)
    except Exception as e:
        # Can't create lock file, so something must be seriously wrong
        logger.exception(
            f"Unable to create lock file {GravisNames.LOCK} in {incoming_case}"
        )
        job.status = "Fail"
        job.error_description = e
        job.save()
        return False

    try:
        error_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        logger.exception(f"Cannot create error folder for {incoming_case}")
        job.status = "Fail"
        job.error_description = e
        job.save()
        return False

    status, new_case = load_json(incoming_case, new_folder, error_folder)
    if not status:
        process_error_folder(new_case, incoming_case, error_folder, lock)
        job.status = "Fail"
        job.error_description = f"Error loading study.json from {incoming_case}."
        job.save()
        return False

    # Create directories for further processing.
    try:
        input_dest_folder.mkdir(parents=True, exist_ok=False)
        processed_dest_folder.mkdir(parents=True, exist_ok=False)
        findings_dest_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        logger.exception(
            f"Cannot create one of the processing folders for {incoming_case}"
        )
        process_error_folder(new_case, incoming_case, error_folder, lock)
        job.status = "Fail"
        job.error_description = e
        job.save()
        return False

    # Move files
    if not dicom_set_utils.move_files(incoming_case, input_dest_folder):
        # new_case.delete()
        process_error_folder(new_case, incoming_case, error_folder, lock)
        job.status = "Fail"
        job.error_description = (
            f"Error moving files from {incoming_case} to {input_dest_folder}"
        )
        job.save()
        return False

    register_dicom_set_success, error = dicom_set_utils.register(
        str(input_dest_folder), new_case, "Incoming", job_id, "ORI"
    )
    if not register_dicom_set_success:
        process_error_folder(new_case, incoming_case, error_folder, lock)
        # Delete associated case from db
        # new_case.delete()
        job.status = "Fail"
        job.error_description = error
        job.save()
        return False

    try:
        lock.free()
    except Exception as e:
        logger.exception(
            f"Unable to remove lock file {lock_file_path}" in {incoming_case}
        )  # handle_error
        # new_case.status = Case.CaseStatus.ERROR
        # new_case.case_location = str(error_folder)
        # new_case.save()
        job.status = "Fail"
        job.error_description = e
        job.save()
        return False

    try:
        # Delete .complete and empty folder from incoming
        # os.unlink(complete_file_path)
        os.rmdir(incoming_case)
        os.rmdir(error_folder)
    except Exception as e:
        logger.exception(
            f"Exception during deleting empty folder: {incoming_case} or {error_folder}"
        )
        # new_case.status = Case.CaseStatus.ERROR
        # new_case.case_location = str(error_folder)
        # new_case.save()
        job.status = "Fail"
        job.error_description = e
        job.save()
        return False

    new_case.status = Case.CaseStatus.QUEUED
    new_case.save()
    job.status = "Success"
    job.case = new_case
    job.dicom_set = new_case.dicom_sets.get(origin="Incoming")
    job.save()
    print(new_case.status)
    logger.info(f"Done Processing {incoming_case}")
    return True


def scan_incoming_folder():
    # TODO: check if it exists, add more checks in general
    f = GravisNames.COMPLETE
    try:
        incoming = Path(settings.INCOMING_FOLDER)
        if incoming.exists():
            folder_paths = [
                Path(d)
                for d in os.scandir(incoming)
                if d.is_dir() and Path(os.path.join(d, f)).exists()
            ]
        else:
            logger.exception(f"Incoming folder {incoming} does not exist.")

        for incoming_case in list(folder_paths):
            try:
                # Delete .complete so the folder will not be included in another job
                complete_file_path = Path(incoming_case) / f
                os.unlink(complete_file_path)

            except Exception as e:
                logger.exception(
                    f"Exception during deleting .complete from {incoming_case}"
                )

            # create a job for copying file from incoming to input folder:
            try:
                # dicom_set = case.dicom_sets.get(origin="Incoming")
                new_job = ProcessingJob(
                    # docker_image="gravis-processing",
                    # dicom_set=dicom_set,
                    category="CopyDICOMSet",
                    parameters=dict(incoming_case=str(incoming_case)),
                    # case=case,
                    status="Pending",
                )
                new_job.save()
            except Exception as e:
                logger.exception(
                    f"Exception creating a new copying job for {incoming_case} "
                )
            else:
                try:
                    result = django_rq.enqueue(
                        process_folder,
                        new_job.id,
                        incoming_case,
                        on_success=report_success,
                        on_failure=report_failure,
                    )
                    new_job.rq_id = result.id
                    new_job.save()
                except Exception as e:
                    new_job.error_description = e
                    new_job.save()
                    # process_job_error(new_job.id, e)
                    logger.exception(
                        f"Exception enqueueing a new copying job for {incoming_case} "
                    )
    except Exception as e:
        logger.exception(
            f"Problem processing incoming folder {str(incoming)}. Error: {e}."
        )


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


def trigger_queued_cases():
    # print("trigger_queued_cases()")
    cases = Case.objects.filter(status=Case.CaseStatus.QUEUED)
    for case in cases:
        case.status = Case.CaseStatus.PROCESSING
        case.save()
        dicom_set = case.dicom_sets.get(origin="Incoming")
       
        try:            
            new_job = ProcessingJob(
                docker_image="gravis-processing",
                dicom_set=dicom_set,
                category="DICOMSet",
                case=case,
                status="Pending",
            )
            new_job.save()
        except Exception as e:
            case.status = Case.CaseStatus.ERROR
            case.save()
            logger.exception(
                f"Exception creating a new processing job for {dicom_set.set_location} "
            )
            continue

        try:
            main_processing_job = django_rq.enqueue(
                docker_utils.do_docker_job,
                new_job.id,
                on_success=create_sub_previews,
                on_failure=report_failure,
            )
            new_job.rq_id = main_processing_job.id
            new_job.save()
        except Exception as e:
            docker_utils.process_job_error(new_job.id, e)
            logger.exception(
                f"Exception enqueueing a new processing job for {dicom_set.set_location} "
            )
            continue

        try:            
            job = ProcessingJob(
                status="CREATED", 
                category="CINE", 
                dicom_set=dicom_set,
                case = case,
                parameters={})
            job.save()
            result = django_rq.enqueue(
                do_job,
                args=(GeneratePreviewsJob,job.id),
                # job_timeout=60*60*4,
                on_success=report_success,
                on_failure=report_failure,
                depends_on=main_processing_job
            )
            job.rq_id = result.id
            job.save()
        except Exception as e:
            case.status = Case.CaseStatus.ERROR
            case.save()
            logger.exception(
                f"Exception creating a new cine generation processing job for {dicom_set.set_location} "
            )            


def delete_cases():
    try:
        cases = Case.objects.filter(status="DEL")
        cases_locations_to_delete = []
        for case in cases:
            print(f"Marked for deletion {case.id} {case.case_location}")
            cases_locations_to_delete.append(case.case_location)
        cases.delete()
        for case_location in cases_locations_to_delete:
            shutil.rmtree(case_location)
        
    except Exception as e:
        print(e)


def watch():
    logger.info("Incoming watcher booted.")
    while True:
        sleep(settings.INCOMING_SCAN_INTERVAL)
        try:
            scan_incoming_folder()
        except:
            logger.exception("Failure in incoming")

        try:
            trigger_queued_cases()
        except:
            logger.exception("Error in queuing.")

        try:
            delete_cases()
        except:
            logger.error("Error in deleting.")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
