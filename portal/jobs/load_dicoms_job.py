from typing import Tuple
from .work_job import WorkJobView
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from .docker_utils import do_docker_job
from loguru import logger
from pathlib import Path
from loguru import logger
from pathlib import Path
import shutil
import os, json
from django.db import transaction

from django.conf import settings

import portal.jobs.dicomset_utils as dicomset_utils
from portal.models import Case, ProcessingJob
from common.constants import GravisNames, GravisFolderNames
import common.helper as helper

class LoadDicomsJob(WorkJobView):
    type = "LoadDICOMSet"

    @classmethod
    def do_job(cls, job):
        process_folder(job)
        return ({},[])

def process_folder(job: ProcessingJob):
    incoming_case = Path(job.parameters["incoming_case"])

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
    lock = helper.FileLock(lock_file_path)

    try:
        error_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        raise Exception(f"Cannot create error folder for {incoming_case}")

    status, new_case = load_json(incoming_case, new_folder, error_folder)
    if not status:
        process_error_folder(new_case, incoming_case, error_folder, lock)
        raise Exception(f"Error loading study.json from {incoming_case}.")
    
    # Create directories for further processing.
    try:
        input_dest_folder.mkdir(parents=True, exist_ok=False)
        processed_dest_folder.mkdir(parents=True, exist_ok=False)
        findings_dest_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        process_error_folder(new_case, incoming_case, error_folder, lock)
        raise Exception(
            f"Cannot create one of the processing folders for {incoming_case}"
        )

    # Move files
    if not dicomset_utils.move_files(incoming_case, input_dest_folder):
        # new_case.delete()
        process_error_folder(new_case, incoming_case, error_folder, lock)
        raise Exception(f"Error moving files from {incoming_case} to {input_dest_folder}")

    register_dicom_set_success, error = dicomset_utils.register(
        str(input_dest_folder), new_case, "Incoming", job.id, "ORI"
    )
    if not register_dicom_set_success:
        process_error_folder(new_case, incoming_case, error_folder, lock)
        raise Exception(error)

    lock.free()

    try:
        # Delete .complete and empty folder from incoming
        # os.unlink(complete_file_path)
        os.rmdir(incoming_case)
        os.rmdir(error_folder)
    except Exception as e:
        raise Exception(
            f"Exception during deleting empty folder: {incoming_case} or {error_folder}"
        )

    new_case.status = Case.CaseStatus.QUEUED
    new_case.save()
    job.status = "Success"
    job.case = new_case
    job.dicom_set = new_case.dicom_sets.get(origin="Incoming")
    job.save()
    
    logger.info(f"Done Processing {incoming_case}")
    return True



def load_json(incoming_case, new_folder, error_folder) -> Tuple[bool, Case]:
    json_name = "study.json"
    incoming_json_file = Path(incoming_case / json_name)

    if not incoming_json_file.exists():
        raise Exception(f"File '{json_name}' missing from {incoming_case}.")

    try:
        with open(incoming_json_file, "r") as f:
            payload = json.load(f)
    except Exception:
        raise Exception(f"Unable to read {json_name} in {incoming_case}.")

    try:
        new_case = Case(
            patient_name=payload.get("patient_name", ""),
            mrn=payload.get("mrn", ""),
            acc=payload.get("acc", ""),
            case_type=payload.get("case_type", ""),
            exam_time=payload.get("exam_time", "1900-01-01 00:00 ET"),
            receive_time=payload.get("receive_time", "1900-01-01 00:00 ET"),
            twix_id=payload.get("twix_id", ""),
            num_spokes=payload.get("num_spokes", ""),
            case_location=str(new_folder),
            settings=payload.get("settings", ""),
            incoming_payload=payload,
            status=Case.CaseStatus.PROCESSING,
        )  # Case(data_location="./data/cases)[UID]")
        with transaction.atomic():
            new_case.save()
            new_case.add_shadow()
    except Exception as e:
        raise Exception(f"Cannot create case for {error_folder}. Exception: {e}")

    study_keys = ["patient_name", "mrn", "acc", "case_type", "exam_time", "twix_id", "num_spokes"]
    # TODO check that values for these fields are valid. If not set status to ERROR/.
    for key in study_keys:
        if key not in payload:
            logger.exception(f"Field {key} is missing from study.json file.")
            return False, new_case

    return True, new_case


def process_error_folder(
    case: Case, incoming_folder: Path, error_folder: Path, lock: Path
):

    dicomset_utils.move_files(incoming_folder, error_folder)
    if case is not None:
        case.status = Case.CaseStatus.ERROR
        case.case_location = str(error_folder)
        case.save()
    try:
        lock.free()
        # os.unlink(complete_file_path)
        os.rmdir(incoming_folder)
        # os.rmdir(error_folder)
    except Exception as e:
        raise Exception(
            f"Exception {e} during cleaning stage after moving {incoming_folder} to the {error_folder} folder."
        )
    logger.error(f"Done Processing {incoming_folder} with error.")