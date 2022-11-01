# import logging
from unittest.mock import NonCallableMagicMock
from loguru import logger
from pathlib import Path
import shutil
from time import sleep
import os, json
from typing import Tuple
from uuid import uuid4
import pydicom
import docker

from django.conf import settings
import django_rq
from django.utils import timezone

from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from common.generate_folder_name import generate_folder_name
from common.constants import GravisNames, GravisFolderNames, DockerReturnCodes

import common.helper as helper
import common.config as config

# logging.basicConfig(filename='watch_incoming.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)


# TODO move to a separate file
def register_dicom_set(
    set_path: str, case, origin, type, job_id=None
) -> Tuple[bool, str]:

    # Register DICOM Set
    print("set_path ", set_path)
    try:
        dicom_set = DICOMSet(
            set_location=str(set_path),
            origin=origin,
            type=type,
            case=case,
            processing_job_id=job_id,
        )
        dicom_set.save()
    except Exception as e:
        logger.exception(f"Cannot create a db table for incoming data set {set_path}")
        return (False, e)

    # Register DICOM Instances
    for dcm in Path(set_path).glob("**/*.dcm"):
        if not dcm.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
        except Exception as e:
            logger.exception(
                f"Exception during dicom file reading. Cannot process incoming instance {str(dcm)}"
            )
            return (False, e)
        try:
            instance = DICOMInstance.from_dataset(ds)
            instance.instance_location = str(dcm.relative_to(Path(set_path)))
            instance.dicom_set = dicom_set
            instance.save()
        except Exception as e:
            logger.exception(
                f"Exception during DICOMInstance model creation. Cannot process incoming instance {str(dcm)}"
            )
            return (False, e)
    return (True, "")


def move_files(source_folder: Path, destination_folder: Path):
    try:
        # destination_folder.mkdir(parents=True, exist_ok=True)
        files_to_copy = source_folder.glob("**/*")
        lock_file_path = Path(source_folder) / GravisNames.LOCK
        complete_file_path = Path(source_folder) / GravisNames.COMPLETE
        for file_path in files_to_copy:
            if file_path == lock_file_path or file_path == complete_file_path:
                continue
            dst_path = os.path.join(destination_folder, os.path.basename(file_path))
            shutil.move(
                file_path, dst_path
            )  # ./data/incoming/<Incoming_UID>/ => ./data/cases/<UID>/input/

    except Exception as e:
        logger.exception(
            f"Exception {e} during copying files from {source_folder} to {destination_folder}"
        )
        return False
    return True


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
            case_location=case_location,
            settings=payload.get("settings", ""),
            incoming_payload=payload,
            status=case_status,
        )  # Case(data_location="./data/cases)[UID]")
        new_case.save()
        study_keys = ["patient_name", "mrn", "acc", "case_type", "exam_time", "twix_id"]
        # TODO check that values for these fields are valid. If not set status to ERROR/.
        for key in study_keys:
            if key not in payload:
                return False, new_case
    except Exception as e:
        logger.exception(f"Cannot create case for {error_folder}. Exception: {e}")
        return False, None
    return True, new_case


def process_error_folder(
    case: Case,
    incoming_folder: Path,
    error_folder: Path,
    lock: Path,
    complete_file_path: Path,
):

    move_files(incoming_folder, error_folder)
    if not case is None:
        case.status = Case.CaseStatus.ERROR
        case.case_location = str(error_folder)
        case.save()
    try:
        lock.free()
        os.unlink(complete_file_path)
        os.rmdir(incoming_folder)
        # os.rmdir(error_folder)
    except Exception as e:
        logger.exception(
            f"Exception {e} during cleaning stage after moving {incoming_folder} to the {error_folder} folder."
        )
    logger.error(f"Done Processing {incoming_folder} with error.")


def process_folder(incoming_case: Path):
    # Move from incoming to cases
    logger.info(f"Processing {incoming_case}")

    cases = Path(settings.CASES_FOLDER)
    dest_folder_name = generate_folder_name()
    new_folder = cases / dest_folder_name
    error_folder = Path(settings.ERROR_FOLDER) / dest_folder_name
    input_dest_folder = new_folder / GravisFolderNames.INPUT
    processed_dest_folder = new_folder / GravisFolderNames.PROCESSED
    findings_dest_folder = new_folder / GravisFolderNames.FINDINGS
    complete_file_path = Path(incoming_case) / GravisNames.COMPLETE
    lock_file_path = Path(incoming_case) / GravisNames.LOCK
    if lock_file_path.exists():
        # Series is locked, so another instance might be working on it
        return True

    # Create lock file in the incoming folder and prevent other instances from working on this series
    try:
        lock = helper.FileLock(lock_file_path)
    except:
        # Can't create lock file, so something must be seriously wrong
        logger.exception(
            f"Unable to create lock file {GravisNames.LOCK} in {incoming_case}"
        )
        return False

    try:
        error_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        logger.exception(f"Cannot create error folder for {incoming_case}")
        return False

    status, new_case = load_json(incoming_case, new_folder, error_folder)
    if not status:
        process_error_folder(
            new_case, incoming_case, error_folder, lock, complete_file_path
        )
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
        process_error_folder(
            new_case, incoming_case, error_folder, lock, complete_file_path
        )
        return False

    # Move files
    if not move_files(incoming_case, input_dest_folder):
        # new_case.delete()
        process_error_folder(
            new_case, incoming_case, error_folder, lock, complete_file_path
        )
        return False

    register_dicom_set_success = register_dicom_set(
        str(input_dest_folder), new_case, "Incoming", "ORI"
    )[0]
    if not register_dicom_set_success:
        process_error_folder(
            new_case, incoming_case, error_folder, lock, complete_file_path
        )
        # Delete associated case from db
        # new_case.delete()
        return False

    try:
        lock.free()
    except Exception:
        logger.exception(
            f"Unable to remove lock file {lock_file_path}" in {incoming_case}
        )  # handle_error
        # new_case.status = Case.CaseStatus.ERROR
        # new_case.case_location = str(error_folder)
        # new_case.save()
        return False

    try:
        # Delete .complete and empty folder from incoming
        os.unlink(complete_file_path)
        os.rmdir(incoming_case)
        os.rmdir(error_folder)
    except Exception as e:
        logger.exception(
            f"Exception during deleting empty folder: {incoming_case} or {error_folder}"
        )
        # new_case.status = Case.CaseStatus.ERROR
        # new_case.case_location = str(error_folder)
        # new_case.save()
        return False

    new_case.status = Case.CaseStatus.QUEUED
    new_case.save()
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
            process_folder(incoming_case)
    except Exception as e:
        logger.exception(
            f"Problem processing incoming folder {str(incoming)}. Error: {e}."
        )


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
        try:
            dicom_set = case.dicom_sets.get(origin="Incoming")
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
        else:
            try:
                result = django_rq.enqueue(
                    do_docker_job,
                    new_job.id,
                    on_success=report_success,
                    on_failure=report_failure,
                )
                new_job.rq_id = result.id
                new_job.save()
            except Exception as e:
                process_job_error(new_job.id, e)
                logger.exception(
                    f"Exception enqueueing a new processing job for {dicom_set.set_location} "
                )


def do_docker_job(job_id):
    # TODO move docker stuff in a separate file.
    # Run the container and handle errors of running the container
    processing_success = True

    try:
        job: ProcessingJob = ProcessingJob.objects.get(id=job_id)
    except Exception as e:
        logger.exception(f"ProcessingJob with id {job_id} does not exist.")
        return False

    try:
        docker_client = docker.from_env()

        job.status = "Processing"
        job.save()
        docker_tag = job.docker_image

        input_folder = job.case.case_location + "/input/"
        # Volume for subtracted slices
        output_folder = job.case.case_location + "/processed/" + str(uuid4())

        volumes = {
            input_folder: {"bind": "/tmp/data/", "mode": "rw"},
            output_folder: {"bind": "/tmp/output/", "mode": "rw"},
        }

        # settings = {"n_slices": 20, "angle_step": 10, "full_rotation_flag": False}
        environment = dict(
            GRAVIS_IN_DIR="/tmp/data/",
            GRAVIS_OUT_DIR="/tmp/output/",
            GRAVIS_ANGLE_STEP=10,
            GRAVIS_MIP_FULL_ROTATION=False,
            GRAVIS_NUM_BOTTOM_SLICES=20,
            DOCKER_RETURN_CODES=DockerReturnCodes.toDict(),
        )

        Path(output_folder).mkdir(parents=True, exist_ok=False)
    except Exception as e:
        process_job_error(job_id, e)

        logger.exception(f"Exception setting up job parameters for {input_folder}")
        processing_success = False
    else:
        try:
            logger.info(":::Docker job begin:::")
            logger.info(
                {
                    "docker_tag": docker_tag,
                    "volumes": volumes,
                    "environment": environment,
                }
            )

            container = docker_client.containers.run(
                docker_tag,
                volumes=volumes,
                environment=environment,
                # user=f"{os.getuid()}:{os.getegid()}",
                # group_add=[os.getegid()],
                detach=True,
            )

            docker_result = container.wait()
            logger.info("DOCKER RESULTS: ", docker_result)

            logger.info(
                "=== MODULE OUTPUT - BEGIN ========================================"
            )
            if container.logs() is not None:
                logs = container.logs().decode("utf-8")
                logger.info(logs)
            logger.info(
                "=== MODULE OUTPUT - END =========================================="
            )

            # Check if the processing was successful (i.e., container returned exit code 0)
            exit_code = docker_result.get("StatusCode")
            if exit_code != 0:
                error_description = f"Error while running container {docker_tag} - exit code {exit_code}. Value {DockerReturnCodes(exit_code).name}."
                process_job_error(job_id, error_description)
                logger.error(error_description)  # handle_error
                processing_success = False

            # Remove the container now to avoid that the drive gets full
            container.remove()

        except docker.errors.APIError as e:
            # Something really serious happened
            process_job_error(job_id, e)
            logger.error(
                f"API error while trying to run Docker container, tag: {docker_tag}"
            )  # handle_error
            processing_success = False

        except docker.errors.ImageNotFound as e:
            process_job_error(job_id, e)
            logger.error(
                f"Error running docker container. Image for tag {docker_tag} not found."
            )  # handle_error
            processing_success = False

        except Exception as e:
            process_job_error(job_id, e)
            logger.error(
                f"Error running docker container. Image for tag {docker_tag} not found."
            )  # handle_error
            processing_success = False

    if processing_success:
        # TODO figure out sub/mip from dicom tags
        job.complete = True
        try:
            register_dicom_set_success, error = register_dicom_set(
                output_folder + "/sub", job.case, "Processed", "SUB", job_id
            )
            if not register_dicom_set_success:
                process_job_error(job_id, error)
                return False
            register_dicom_set_success, error = register_dicom_set(
                output_folder + "/mip", job.case, "Processed", "MIP", job_id
            )
            if not register_dicom_set_success:
                process_job_error(job_id, error)
                return False
            job.status = "Success"
            # job.dicom_set = dicom_set
            job.case.status = Case.CaseStatus.READY
            job.case.save()
            job.save()
        except Exception as e:
            process_job_error(job_id, e)
            logger.error(
                f"Error creating output DICOMSet for {input_folder} for case {job.case}."
            )  # handle_error
            processing_success = False

    return processing_success


def process_job_error(job_id, error_description):
    logger.error(error_description)
    try:
        job: ProcessingJob = ProcessingJob.objects.get(id=job_id)
    except Exception as e:
        logger.exception(f"ProcessingJob with id {job_id} does not exist.")
        return False
    folder_name = os.path.basename(os.path.dirname(job.case.case_location))
    print("ERROR FOLDER!!!: ", folder_name)
    move_files(Path(job.case.case_location), Path(settings.ERROR_FOLDER) / folder_name)
    job.case.status = Case.CaseStatus.ERROR
    job.case.save()
    job.status = "Fail"
    job.error_description = error_description
    job.save()


def watch():
    while True:
        sleep(settings.INCOMING_SCAN_INTERVAL)
        try:
            scan_incoming_folder()
        except:
            logger.error("Failure in incoming")

        try:
            trigger_queued_cases()
        except:
            logger.error("Error in queuing.")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
