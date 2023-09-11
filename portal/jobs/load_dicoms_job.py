from datetime import datetime
import gzip
import subprocess
from typing import Tuple
from .work_job import WorkJobView
from portal.models import Case, Tag
from loguru import logger
from pathlib import Path
import shutil
import os, json
import stat
from django.db import transaction
import pydicom
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
        logs_folder = new_folder / GravisFolderNames.LOGS
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
                status, new_case = load_json(incoming_folder, new_folder)
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
                logs_folder.mkdir(parents=True, exist_ok=False)
            except:
                raise Exception(
                    f"Cannot create one of the processing folders for {incoming_folder}"
                )

            # Move files
            if not dicomset_utils.move_files(incoming_folder, input_dest_folder):
                # new_case.delete()
                raise Exception(f"Error moving files from {incoming_folder} to {input_dest_folder}")
            
            for f in [processed_dest_folder, findings_dest_folder, input_dest_folder, new_folder, logs_folder]:
                f.chmod(f.stat().st_mode | stat.S_IROTH | stat.S_IXOTH) # TODO: is this necessary?

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

        # Get a sample dicom. 
        try:
            example_dcm = next(incoming_folder.glob("**/*.dcm"))
            fp = open(example_dcm,"rb")
        except StopIteration:
            try: # the dicoms might be gzipped
                example_dcm = next(incoming_folder.glob("**/*.dcm.gz"))
                fp = gzip.open(example_dcm,"r")
            except StopIteration:
                raise Exception("Directory does not contain any .dcm files.")
        
        with fp:
            new_case = case_from_payload(override_json, new_folder, fp)

        job.case = new_case
        job.save()
        # Create directories for further processing.
        try:
            processed_dest_folder.mkdir(parents=True, exist_ok=False)
            findings_dest_folder.mkdir(parents=True, exist_ok=False)
        except:
            raise Exception(f"Cannot create one of the processing folders for {incoming_folder}")

        try:
            shutil.copytree(incoming_folder, input_dest_folder)
            # Unzip any zipped dicoms.
            zipped_dicoms = list(input_dest_folder.glob("*.dcm.gz"))
            if zipped_dicoms:
                logger.info("Unzipping dicoms.")
                subprocess.run(["gzip", "-d", *zipped_dicoms], stdout=subprocess.PIPE, check=True)
        except: 
            raise Exception(f"Error copying files from {incoming_folder} to {input_dest_folder}")

        for f in [processed_dest_folder, findings_dest_folder, input_dest_folder, new_folder]:
            f.chmod(f.stat().st_mode | stat.S_IROTH | stat.S_IXOTH) # TODO: is this necessary?

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

def case_from_payload(payload, new_folder, example_dcm):
    def getvals(*args):
        return {k:payload.get(k,"") for k in args}
    try:
        new_case = Case(
            **getvals("patient_name", "mrn", "acc", "twix_id", "num_spokes", "settings"),
            exam_time = payload.get("exam_time", None),
            receive_time = payload.get("receive_time", datetime.now().astimezone()),
            case_location = str(new_folder),
            incoming_payload = payload,
            status = Case.CaseStatus.PROCESSING,
        )
        for choice in Case.CaseType.choices:
            if payload.get("case_type") in choice:
                new_case.case_type = choice[0]
        if not new_case.exam_time:
            ds = pydicom.dcmread(example_dcm, specific_tags=("StudyDate", "StudyTime"), stop_before_pixels=True)
            new_case.exam_time = datetime.combine(
                pydicom.valuerep.DA(ds.StudyDate), pydicom.valuerep.TM(ds.StudyTime)
            )

        with transaction.atomic():
            new_case.save()
            for tag in payload.get("tags",[]):
                t, created = Tag.objects.get_or_create(name=tag)
                if created:
                    t.save()
                new_case.tags.add(t)
            new_case.add_shadow()
        return new_case
    except:
        raise Exception(f"Cannot create case for {payload}.")

def load_json(incoming_folder, new_folder) -> Tuple[bool, Case]:
    json_name = "study.json"
    incoming_json_file = Path(incoming_folder / json_name)

    if not incoming_json_file.exists():
        raise Exception(f"File '{json_name}' missing from {incoming_folder}.")

    try:
        with open(incoming_json_file, "r") as f:
            payload = json.load(f)
    except Exception:
        raise Exception(f"Unable to read {json_name} in {incoming_folder}.")

    try:
        example_dcm = next(incoming_folder.glob("**/*.dcm"))
    except StopIteration:
        raise Exception("Directory does not contain any .dcm files.")

    new_case = case_from_payload(payload, new_folder, example_dcm)
    study_keys = ["patient_name", "mrn", "acc", "case_type"]
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