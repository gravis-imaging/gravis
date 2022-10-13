import logging
from pathlib import Path
import shutil
from time import sleep
import os, json
from unicodedata import category
from uuid import uuid4
import pydicom
import docker

from django.conf import settings
import django_rq

from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from common.generate_folder_name import generate_folder_name
from common.constants import gravis_names, gravis_folder_names
import common.helper as helper

logger = logging.getLogger(__name__)


def process_folder(incoming_case: Path):
    # Move from incoming to cases
    print(f"Processing {incoming_case}")

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
            type="Incoming",
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

    # Register DICOM Instances
    for dcm in incoming_case.glob("**/*.dcm"):
        if not dcm.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
        except Exception as e:
            logger.exception(
                f"Exception during dicom file reading. Cannot process incoming instance {str(dcm)}"
            )
            move_files(incoming_case, error_folder)
            # Delete associated case from db
            new_case.delete()
            return False

        try:
            instance = DICOMInstance(
                instance_location=str(dcm.relative_to(incoming_case)),
                study_uid=ds.StudyInstanceUID,
                series_uid=ds.SeriesInstanceUID,
                instance_uid=ds.SOPInstanceUID,
                json_metadata=ds.to_json(),
                dicom_set=dicom_set,
            )
            instance.save()
        except Exception as e:
            logger.exception(
                f"Exception during DICOMInstance model creation. Cannot process incoming instance {str(dcm)}"
            )
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

    print(f"Done Processing {incoming_case}")
    return True


def move_files(source_folder, destination_folder):
    try:
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


# def trigger_queued_cases():
#     print("AAA trigger_queued_cases")


#     cases = Path(settings.CASES_FOLDER)
#     # f = gravis_names.COMPLETE
#     input = gravis_folder_names.INPUT
#     folder_paths = [
#         Path(d)
#         for d in os.scandir(cases)
#         if d.is_dir() and Path(os.path.join(d, input)).exists()
#     ]
#     # print(folder_paths)
#     client = docker.from_env()
#     containers = {}
#     for folder in folder_paths:
#         object = Case.objects.filter(case_location=folder)
#         if len(object) > 0 and object[0].status == Case.CaseStatus.QUEUED:
#             # process
#             object[0].status = Case.CaseStatus.PROCESSING
#             object[0].save()
#             container = client.containers.run(
#                 image="gravis-processing",
#                 # name="gp-worker",
#                 environment=["GRAVIS_IN_DIR=/data"],
#                 volumes=[
#                     str(folder)+":/data",
#                 ],
#                 detach=True,
#             )
#             containers[container] = object[0]

#             container.logs()

#     # containers = client.containers.list(all=True)
#     # print("KKK ", containers)
#     for container in containers:
#         container_state = container.attrs["State"]
#         if container_state["Status"] == "exited":
#             object = containers[container]
#             object.status = Case.CaseStatus.READY
#             object.save()


def trigger_queued_cases():
    print("trigger_queued_cases()")
    cases = Case.objects.filter(status = Case.CaseStatus.QUEUED)
    for case in cases:
        try:
            dicom_set=case.dicom_sets.get(type="Incoming")
            new_job = ProcessingJob(
                docker_image="gravis-processing",
                dicom_set=dicom_set,
                category="DICOMSet",
                case=case,
            )
        except Exception as e:
            logger.exception(
                f"Exception creating a new processing job for {dicom_set.set_location} "
            )
        new_job.save()
        result = django_rq.enqueue(do_docker_job, new_job.id)
        new_job.rq_id = result.id
        new_job.save()


def do_docker_job(job_id):
    print(":::Docker job begin:::")
    docker_client = docker.from_env()

    job: ProcessingJob = ProcessingJob.objects.get(id=job_id)

    job.case.status = Case.CaseStatus.PROCESSING
    job.case.save()

    input_folder = job.case.case_location + "/input/"
    output_folder = job.case.case_location + "/processed/" + str(uuid4())

    volumes = {
        input_folder: {"bind": "/tmp/data/", "mode": "rw"},
        output_folder: {"bind": "/tmp/output/", "mode": "rw"},
    }
    try:
        Path(output_folder).mkdir(parents=True, exist_ok=False) # ???    
    except Exception as e:
         logger.exception(
                    f"Exception creating a folder {output_folder}"
                )

    environment = dict(GRAVIS_IN_DIR="/tmp/data/", GRAVIS_OUT_DIR="/tmp/output/")

    container = docker_client.containers.run(
        job.docker_image,
        volumes=volumes,
        environment=environment,
        # user=f"{os.getuid()}:{os.getegid()}",
        # group_add=[os.getegid()],
        detach=True,
    )

    print("Docker is running...")
    docker_result = container.wait()
    print(docker_result)
    print("=== MODULE OUTPUT - BEGIN ========================================")
    if container.logs() is not None:
        logs = container.logs().decode("utf-8")
        print(logs)
    print("=== MODULE OUTPUT - END ==========================================")
    job.complete = True
    dicom_set = DICOMSet(
        set_location=output_folder, type="Processed", case=job.case
    )
    dicom_set.save()
    job.dicom_set = dicom_set
    job.case.status = Case.CaseStatus.READY
    job.case.save()
    job.save()


def watch():
    while True:
        sleep(settings.INCOMING_SCAN_INTERVAL)
        try:
            scan_incoming_folder()
            trigger_queued_cases()
        except:
            logging.error("Failure in incoming")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
