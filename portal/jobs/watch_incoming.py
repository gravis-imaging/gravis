import logging
from pathlib import Path
import shutil
from time import sleep
import os, json
import pydicom

from django.conf import settings

from portal.models import Case, DICOMInstance, DICOMSet
from common.generate_folder_name import generate_folder_name
from common.constants import gravis_names, gravis_folder_names
import common.helper as helper


def process_folder(incoming_case: Path):
    cases = Path(settings.CASES_FOLDER)
    error_folder = Path(settings.ERROR_FOLDER)
    # Move
    print(f"Processing {incoming_case}")
    dest_folder_name = generate_folder_name()
    new_folder = cases / dest_folder_name
    input_dest_folder = new_folder / gravis_folder_names.INPUT
    processed_dest_folder = new_folder / gravis_folder_names.PROCESSED
    findings_dest_folder = new_folder / gravis_folder_names.FINDINGS

    lock_file = Path(incoming_case) / gravis_names.LOCK
    if lock_file.exists():
        # Series is locked, so another instance might be working on it
        return True

    # Create lock file in the incoming folder and prevent other instances from working on this series
    try:
        lock = helper.FileLock(lock_file)
    except:
        # Can't create lock file, so something must be seriously wrong
        print(
            f"Unable to create lock file {lock_file} in {incoming_case}"
        )  # handle_error
        return False

    # Read study.jon from the incoming folder.
    json_name = "study.json"
    incoming_json_file = Path(input_dest_folder / json_name)
    try:
        with open(incoming_json_file, "r") as myfile:
            d = myfile.read()
        payload = json.loads(d)
    except Exception:
        print(f"Unable to read {json_name} in {input_dest_folder}.")
        move_files(incoming_case, error_folder)
        return False

    # Create directories for further processing.
    try:
        input_dest_folder.mkdir(parents=True, exist_ok=False)
        processed_dest_folder.mkdir(parents=True, exist_ok=False)
        findings_dest_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        print(f"Exception {e}.")
        print(f"Cannot create one of the processing folders for {incoming_case}")
        return False

    # Move files
    if not move_files(incoming_case, input_dest_folder):
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
        print(f"Exception during Case model creation: {e}")
        print(f"Cannot process incoming data set {incoming_case}")
        print(
            f"Please check that all fields in json file {incoming_json_file} are valid"
        )
        move_files(input_dest_folder, error_folder)
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
        print(f"Exception during DICOMSet model creation: {e}")
        print(f"Cannot create a db table for incoming data set {incoming_case}")
        move_files(input_dest_folder, error_folder)
        # Delete associated case from db
        new_case.delete()
        return False

    # Register DICOM Instances
    for dcm in input_dest_folder.glob("**/*.dcm"):
        if not dcm.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
        except Exception as e:
            print(f"Exception during reading dicom file: {e}")
            print(f"Cannot process incoming instance {str(dcm)}")
            move_files(input_dest_folder, error_folder)
            # Delete associated case from db
            new_case.delete()
            return False

        try:
            instance = DICOMInstance(
                instance_location=str(dcm.relative_to(input_dest_folder)),
                study_uid=ds.StudyInstanceUID,
                series_uid=ds.SeriesInstanceUID,
                instance_uid=ds.SOPInstanceUID,
                json_metadata=ds.to_json(),
                dicom_set=dicom_set,
            )
            instance.save()
        except Exception as e:
            print(f"Exception during DICOMInstance model creation: {e}")
            print(f"Cannot process incoming instance {str(dcm)}")
            move_files(input_dest_folder, error_folder)
            # Delete associated case from db
            new_case.delete()
            return False

    try:
        lock.free()
    except Exception:
        print(
            f"Unable to remove lock file {lock_file}" in {incoming_case}
        )  # handle_error
        return False

    new_case.status = Case.CaseStatus.QUEUED
    new_case.save()

    print(f"Done Processing {incoming_case}")
    return True


def move_files(source_folder, destination_folder):
    try:
        files_to_copy = source_folder.glob("**/*")
        for file_path in files_to_copy:
            dst_path = os.path.join(destination_folder, os.path.basename(file_path))
            shutil.move(
                file_path, dst_path
            )  # ./data/incoming/<Incoming_UID>/ => ./data/cases/<UID>/input/
        # Delete empty folder from incoming
        os.rmdir(source_folder)
    except Exception as e:
        print(
            f"Exception {e} during copying files from {source_folder} to {destination_folder}"
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


def trigger_queued_cases():
    # TODO: Fetch cases from DB that have status QUEUED and launch RQ
    pass


def watch():
    while True:
        sleep(settings.INCOMING_SCAN_INTERVAL)
        try:
            scan_incoming_folder()
            trigger_queued_cases()
        except:
            logging.error("Failure in incoming")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
