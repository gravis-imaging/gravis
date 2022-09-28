import logging
from datetime import timedelta
from pathlib import Path
import shutil
from time import sleep
import os, json

import django_rq
from django_rq.queues import get_queue
from django.conf import settings
import pydicom

from portal.models import Case, DICOMInstance, DICOMSet

logger = logging.getLogger(__name__)


def do_watch():
    # print("AAA do_watch")
    data_folder = Path(settings.DATA_FOLDER)
    incoming = data_folder / "incoming"
    cases = data_folder / "cases"

    f = ".complete"
    folder_paths = [ Path(d) for d in os.scandir(incoming) if d.is_dir() and Path(os.path.join(d,f)).exists() ]
  
    for incoming_case in list(folder_paths):

        # Move
        print(f"Processing {incoming_case}")
        new_folder = cases / incoming_case.stem
        dest_folder = new_folder / "input"
        new_folder.mkdir(parents=True, exist_ok=False)
        shutil.move(incoming_case, dest_folder)  # ./data/incoming/<foo>/ => ./data/cases/<foo>/input/
       
        # Read study.jon from the incoming folder
        json_name = 'study.json'
        incoming_json_file = Path(dest_folder / json_name)
        try:
            with open(incoming_json_file, 'r') as myfile:
                d=myfile.read()
            payload = json.loads(d)
        except Exception:
            print(f"Unable to read {json_name} in {dest_folder}.")
            continue

        # TODO: if case is in the database erase it first ?
        # Register Case
        try:
            new_case = Case(
                patient_name = payload["patient_name"],
                mrn = payload["mrn"],
                acc = payload["acc"],
                case_type = payload["case_type"],
                exam_time = payload["exam_time"],
                receive_time = payload["receive_time"],
                twix_id = payload["twix_id"],
                case_location=str(new_folder),
                incoming_payload = payload,
            )  # Case(data_location="/data/cases/<foo>")
            new_case.save()
        except Exception as e:
            print(f"Exception during Case model creation: {e}")
            print(f"Cannot process incoming data set {incoming_case}")
            continue

        # Register Dicom Set
        try:
            dicom_set = DICOMSet(
                set_location = str(dest_folder),
                type = "Incoming",
                case = new_case,
            )
            dicom_set.save()
        except Exception as e:
            print(f"Exception during DICOMSet model creation: {e}")
            print(f"Cannot process incoming data set {incoming_case}")
            continue
        
        # Register Dicom Instances
        for dcm in dest_folder.glob("**/*"):
            if not dcm.is_file():
                continue
            try:
                ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
            except:
                continue
            try:
                instance = DICOMInstance(
                    instance_location=str(dcm.relative_to(data_folder)),
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


def watch():
    while True:
        sleep(1)
        try:
            do_watch()
        except:
            logging.error("Failure in incoming")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
