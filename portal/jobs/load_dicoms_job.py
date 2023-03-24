from typing import Tuple
from .work_job import WorkJobView
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from loguru import logger
from pathlib import Path
from loguru import logger
from pathlib import Path
import shutil
import os, json
import stat
from django.db import transaction

from django.conf import settings

import portal.jobs.dicomset_utils as dicomset_utils
from common.constants import GravisNames, GravisFolderNames
import common.helper as helper


class LoadDicomsJob(WorkJobView):
    type = "LoadDICOMSet"
    queue = "cheap"
    
    @classmethod
    def do_job(cls, job):
        incoming_folder = Path(job.parameters["incoming_folder"])

        logger.info(f"Processing {incoming_folder}")

        cases = Path(settings.CASES_FOLDER)
        dest_folder_name = helper.generate_folder_name()
        new_folder = cases / dest_folder_name
        error_folder = Path(settings.ERROR_FOLDER) / dest_folder_name
        input_dest_folder = new_folder / GravisFolderNames.INPUT
        processed_dest_folder = new_folder / GravisFolderNames.PROCESSED
        findings_dest_folder = new_folder / GravisFolderNames.FINDINGS
        # complete_file_path = Path(incoming_folder) / GravisNames.COMPLETE
        lock_file_path = Path(incoming_folder) / GravisNames.LOCK

        lock = None
        new_case = None

        try:
            # Move from incoming to cases
            if lock_file_path.exists():
                # Series is locked, so another instance might be working on it
                return

            # Create lock file in the incoming folder and prevent other instances from working on this series
            lock = helper.FileLock(lock_file_path)
            
            try:
                status, new_case = load_json(incoming_folder, new_folder, error_folder)
            except:
                raise Exception(f"Error loading study.json from {incoming_folder}.")
            
            if not status:
                raise Exception(f"Error loading study.json from {incoming_folder}.")
            
            job.case = new_case
            job.save()
            # Create directories for further processing.
            try:
                input_dest_folder.mkdir(parents=True, exist_ok=False)
                processed_dest_folder.mkdir(parents=True, exist_ok=False)
                findings_dest_folder.mkdir(parents=True, exist_ok=False)
                # TODO: do we really need open permissions like this?
                new_folder.chmod(new_folder.stat().st_mode | stat.S_IROTH | stat.S_IXOTH)
            except:
                raise Exception(
                    f"Cannot create one of the processing folders for {incoming_folder}"
                )

            # Move files
            if not dicomset_utils.move_files(incoming_folder, input_dest_folder):
                # new_case.delete()
                raise Exception(f"Error moving files from {incoming_folder} to {input_dest_folder}")
            
            input_dest_folder.chmod(input_dest_folder.stat().st_mode | stat.S_IROTH | stat.S_IXOTH)

            dicomset_utils.register(
                input_dest_folder, new_case, "Incoming", job.id, "ORI"
            )
            # job.dicom_set = new_case.dicom_sets.get(origin="Incoming")
            job.save()

            lock.free()
            try:
                os.rmdir(incoming_folder)
            except Exception as e:
                logger.exception(f"Exception during deleting empty folder: {incoming_folder}")
                # Don't actually throw, this case is probably fine

            new_case.status = Case.CaseStatus.QUEUED
            new_case.save()
            job.status = "Success"
            job.save()
            
            logger.info(f"Done loading {incoming_folder}")
        except Exception as e:
            move_to_error_folder(new_case, incoming_folder, error_folder, lock)
            if new_case:
                new_case.case_location = str(error_folder)
                new_case.save()
            raise e


class CopyDicomsJob(WorkJobView):
    type = "CopyDICOMSet"
    queue = "cheap"
    
    @classmethod
    def do_job(cls, job):
        incoming_folder = Path(job.parameters["incoming_folder"])
        override_json = job.parameters["study_json"]
        logger.info(f"Processing {incoming_folder}")

        cases = Path(settings.CASES_FOLDER)
        dest_folder_name = helper.generate_folder_name()
        new_folder = cases / dest_folder_name
        input_dest_folder = new_folder / GravisFolderNames.INPUT
        processed_dest_folder = new_folder / GravisFolderNames.PROCESSED
        findings_dest_folder = new_folder / GravisFolderNames.FINDINGS

        new_case = case_from_payload(override_json, new_folder)
        job.case = new_case
        job.save()
        # Create directories for further processing.
        try:
            processed_dest_folder.mkdir(parents=True, exist_ok=False)
            findings_dest_folder.mkdir(parents=True, exist_ok=False)
            new_folder.chmod(new_folder.stat().st_mode | stat.S_IROTH | stat.S_IXOTH)
        except:
            raise Exception(f"Cannot create one of the processing folders for {incoming_folder}")

        try:
            shutil.copytree(incoming_folder, input_dest_folder)
        except: 
            raise Exception(f"Error copying files from {incoming_folder} to {input_dest_folder}")

        input_dest_folder.chmod(input_dest_folder.stat().st_mode | stat.S_IROTH | stat.S_IXOTH)

        study_json = input_dest_folder / "study.json"
        study_json.touch()
        with open(study_json,"wt") as f:
            json.dump(override_json, f)

        dicomset_utils.register( input_dest_folder, new_case, "Incoming", job.id, "ORI")

        new_case.status = Case.CaseStatus.QUEUED
        job.status = "Success"
        new_case.save()
        job.save()
        
        logger.info(f"Done loading {incoming_folder}")

def case_from_payload(payload, new_folder):
    try:
        new_case = Case(
            patient_name=payload.get("patient_name", ""),
            mrn=payload.get("mrn", ""),
            acc=payload.get("acc", ""),
            case_type=payload.get("case_type", ""),
            exam_time=payload.get("exam_time", "1900-01-01 00:00-05:00"),
            receive_time=payload.get("receive_time", "1900-01-01 00:00-05:00"),
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
        return new_case
    except Exception as e:
        raise Exception(f"Cannot create case for {payload}.")

def load_json(incoming_folder, new_folder, error_folder) -> Tuple[bool, Case]:
    json_name = "study.json"
    incoming_json_file = Path(incoming_folder / json_name)

    if not incoming_json_file.exists():
        raise Exception(f"File '{json_name}' missing from {incoming_folder}.")

    try:
        with open(incoming_json_file, "r") as f:
            payload = json.load(f)
    except Exception:
        raise Exception(f"Unable to read {json_name} in {incoming_folder}.")
    new_case = case_from_payload(payload,new_folder)
    study_keys = ["patient_name", "mrn", "acc", "case_type", "exam_time", "twix_id", "num_spokes"]
    # TODO check that values for these fields are valid. If not set status to ERROR/.
    for key in study_keys:
        if key not in payload:
            logger.error(f"Field {key} is missing from study.json file.")
            return False, new_case

    return True, new_case


def move_to_error_folder(
    case: Case, incoming_folder: Path, error_folder: Path, lock: Path
):
    error_folder.mkdir(parents=True, exist_ok=False)
    dicomset_utils.move_files(incoming_folder, error_folder)
    try:
        if lock is not None:
            lock.free()
        # os.unlink(complete_file_path)
        os.rmdir(incoming_folder)
        # os.rmdir(error_folder)
    except Exception as e:
        raise Exception(
            f"Exception {e} during cleaning stage after moving {incoming_folder} to the {error_folder} folder."
        )
    logger.error(f"Done Processing {incoming_folder} with error.")