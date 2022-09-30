import logging
from pathlib import Path
import shutil
from time import sleep
import os, json
import pydicom

from django.conf import settings

from portal.models import Case, DICOMInstance, DICOMSet
from portal.common.generate_folder_name import generate_folder_name

logger = logging.getLogger(__name__)


def process_folder(incoming_case):
    data_folder = Path(settings.DATA_FOLDER)
    cases = data_folder / "cases"

    # Move
    print(f"Processing {incoming_case}")
    dest_folder_name = generate_folder_name()
    new_folder = cases / dest_folder_name
    input_dest_folder = new_folder / "input"
    processed_dest_folder = new_folder / "processed"
    findings_dest_folder = new_folder / "findings"

    try:
        input_dest_folder.mkdir(parents=True, exist_ok=False)
        processed_dest_folder.mkdir(parents=True, exist_ok=False)
        findings_dest_folder.mkdir(parents=True, exist_ok=False)
    except Exception as e:
        print(f"Exception {e}. Cannot generate {input_dest_folder}")
        return False

    # Move files
    try:
        # TODO: test if there are subfolders
        files_to_copy = incoming_case.glob("**/*")
        for file_path in files_to_copy:
            dst_path = os.path.join(input_dest_folder, os.path.basename(file_path))
            shutil.move(
                file_path, dst_path
            )  # ./data/incoming/<Incoming_UID>/ => ./data/cases/<UID>/input/
    except Exception as e:
        print(
            f"Exception {e} during copying files from {incoming_case} to {input_dest_folder}"
        )
        return False

    # Read study.jon from the incoming folder
    json_name = "study.json"
    incoming_json_file = Path(input_dest_folder / json_name)
    try:
        with open(incoming_json_file, "r") as myfile:
            d = myfile.read()
        payload = json.loads(d)
    except Exception:
        print(f"Unable to read {json_name} in {input_dest_folder}.")
        return False

    # TODO: if case is in the database erase it first ?
    # Register Case
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
            incoming_payload=payload,
        )  # Case(data_location="/data/cases/<foo>")
        new_case.save()
    except Exception as e:
        print(f"Exception during Case model creation: {e}")
        print(f"Cannot process incoming data set {incoming_case}")
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
        print(f"Cannot process incoming data set {incoming_case}")
        return False

    # Register DICOM Instances
    for dcm in input_dest_folder.glob("**/*.dcm"):
        if not dcm.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
        except:
            continue
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
            continue

    print(f"Done Processing {incoming_case}")
    return True


def scan_incoming_folder():

    data_folder = Path(settings.DATA_FOLDER)
    incoming = data_folder / "incoming"

    f = ".complete"
    folder_paths = [
        Path(d)
        for d in os.scandir(incoming)
        if d.is_dir() and Path(os.path.join(d, f)).exists()
    ]

    for incoming_case in list(folder_paths):
        process_folder(incoming_case)
        # TODO: if return is false move it to the error folder
        # else set status of the case to Case.CaseStatus.QUEUED


def watch():
    while True:
        sleep(1)
        try:
            scan_incoming_folder()
        except:
            logging.error("Failure in incoming")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
