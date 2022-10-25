# import logging
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

from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from common.generate_folder_name import generate_folder_name
from common.constants import gravis_names, gravis_folder_names
import common.helper as helper

# logging.basicConfig(filename='watch_incoming.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

def register_dicom_instances(case_path: str, dicom_set) -> Tuple[bool, str]:
    # Register DICOM Instances
    for dcm in Path(case_path).glob("**/*.dcm"):
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
            instance.instance_location = str(dcm.relative_to(Path(case_path)))
            instance.dicom_set = dicom_set
            instance.save()
        except Exception as e:
            logger.exception(
                f"Exception during DICOMInstance model creation. Cannot process incoming instance {str(dcm)}"
            )
            return (False, e)
    return (True, "")

def process_folder(incoming_case: Path):
    # Move from incoming to cases
    logger.info(f"Processing {incoming_case}")

    cases = Path(settings.CASES_FOLDER)
    dest_folder_name = generate_folder_name()
    new_folder = cases / dest_folder_name
    error_folder = Path(settings.ERROR_FOLDER) / dest_folder_name
    input_dest_folder = new_folder / gravis_folder_names.INPUT
    processed_dest_folder = new_folder / gravis_folder_names.PROCESSED
    findings_dest_folder = new_folder / gravis_folder_names.FINDINGS
    complete_file_path = Path(incoming_case) / gravis_names.COMPLETE
    lock_file_path = Path(incoming_case) / gravis_names.LOCK
    if lock_file_path.exists():
        # Series is locked, so another instance might be working on it
        return True

    # Create lock file in the incoming folder and prevent other instances from working on this series
    try:
        lock = helper.FileLock(lock_file_path)
    except:
        # Can't create lock file, so something must be seriously wrong
        logger.exception(
            f"Unable to create lock file {gravis_names.LOCK} in {incoming_case}"
        )
        return False

    # Read study.jon from the incoming folder.
    json_name = "study.json"
    incoming_json_file = Path(incoming_case / json_name)
    try:
        with open(incoming_json_file, "r") as myfile:
            d = myfile.read()
        payload = json.loads(d)
    except Exception:
        logger.exception(f"Unable to read {json_name} in {incoming_case}")
        move_files(incoming_case, error_folder)
        return False

    # Register Case and check that all required fields are in json
    try:
        new_case = Case(
            patient_name=payload["patient_name"],
            mrn=payload["mrn"],
            acc=payload["acc"],
            case_type=payload["case_type"],
            exam_time=payload["exam_time"],
            receive_time=payload["receive_time"],
            twix_id=payload["twix_id"],
            case_location=str(new_folder),
            settings=payload["settings"],
            incoming_payload=payload,
        )  # Case(data_location="./data/cases/[UID]")
        new_case.save()
    except Exception as e:
        logger.exception(f"Cannot process incoming data set {incoming_case}")
        logger.exception(
            f"Please check that all fields in json file {incoming_json_file} are valid"
        )
        move_files(incoming_case, error_folder)
        return False

    # Register DICOM Set
    try:
        dicom_set = DICOMSet(
            set_location=str(input_dest_folder),
            origin="Incoming",
            case=new_case,
        )
        dicom_set.save()
    except Exception as e:
        logger.exception(
            f"Cannot create a db table for incoming data set {incoming_case}"
        )
        move_files(incoming_case, error_folder)
        # Delete associated case from db
        new_case.delete()
        return False

    register_instanceess_success = register_dicom_instances(str(incoming_case), dicom_set)[0]
    if not register_instanceess_success:
        move_files(incoming_case, error_folder)
        # Delete associated case from db
        new_case.delete()
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
        new_case.delete()
        return False

    # Move files
    if not move_files(incoming_case, input_dest_folder):
        new_case.delete()
        return False

    try:
        lock.free()
    except Exception:
        logger.exception(
            f"Unable to remove lock file {lock_file_path}" in {incoming_case}
        )  # handle_error
        return False

    try:
        # Delete .complete and empty folder from incoming
        os.unlink(complete_file_path)
        os.rmdir(incoming_case)
    except Exception as e:
        logger.exception(f"Exception during deleting empty folder: {incoming_case}")
        return False

    new_case.status = Case.CaseStatus.QUEUED
    new_case.save()
    print(new_case.status)

    logger.info(f"Done Processing {incoming_case}")
    return True


def move_files(source_folder: Path, destination_folder: Path):
    try:
        destination_folder.mkdir(parents=True, exist_ok=True)
        files_to_copy = source_folder.glob("**/*")
        lock_file_path = Path(source_folder) / gravis_names.LOCK
        complete_file_path = Path(source_folder) / gravis_names.COMPLETE
        for file_path in files_to_copy:
            if file_path == lock_file_path or file_path == complete_file_path:
                continue
            dst_path = os.path.join(destination_folder, os.path.basename(file_path))
            shutil.move(
                file_path, dst_path
            )  # ./data/incoming/<Incoming_UID>/ => ./data/cases/<UID>/input/

    except Exception as e:
        logger.exception(
            f"Exception during copying files from {source_folder} to {destination_folder}"
        )
        return False
    return True


def scan_incoming_folder():
    incoming = Path(settings.INCOMING_FOLDER)
    f = gravis_names.COMPLETE

    folder_paths = [
        Path(d)
        for d in os.scandir(incoming)
        if d.is_dir() and Path(os.path.join(d, f)).exists()
    ]

    for incoming_case in list(folder_paths):
        process_folder(incoming_case)


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
                error_description = f"Error while running container {docker_tag} - exit code {exit_code}"
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
        job.complete = True
        try:
            dicom_set_sub = DICOMSet(
                set_location=output_folder + "/sub",
                origin="Processed",
                type="SUB",
                case=job.case,
                processing_job_id = job,
            )
            dicom_set_sub.save()
            dicom_set_mip = DICOMSet(
                set_location=output_folder + "/mip",
                origin="Processed",
                type="MIP",
                case=job.case,
                processing_job_id = job,
            )
            dicom_set_mip.save()
            register_instanceess_success, error = register_dicom_instances(output_folder + "/sub", dicom_set_sub)
            if not register_instanceess_success:
                process_job_error(job_id, error)                
                return False
            register_instanceess_success, error = register_dicom_instances(output_folder + "/mip", dicom_set_mip)    
            if not register_instanceess_success:
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
    move_files(Path(job.case.case_location), Path(settings.ERROR_FOLDER))
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
            trigger_queued_cases()
        except:
            logger.error("Failure in incoming")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
