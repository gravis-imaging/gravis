import logging
from datetime import timedelta
from pathlib import Path
from time import sleep

import django_rq
from django_rq.queues import get_queue
from django.conf import settings
import pydicom

from portal.models import Case, DICOMInstance

logger = logging.getLogger(__name__)


def do_watch():
    data_folder = Path(settings.DATA_FOLDER)
    incoming = data_folder / "incoming"
    store = data_folder / "store"

    complete = incoming.glob("*/.complete")
    for k in list(complete):
        # Move
        new_folder = store / k.parent.stem
        dest_folder = new_folder / "input"
        new_folder.mkdir(parents=True, exist_ok=False)
        k.parent.rename(
            dest_folder
        )  # /data/incoming/<foo>/ => /data/store/<foo>/input/

        # Register

        new_case = Case(
            data_location=str(new_folder)
        )  # Case(data_location="/data/store/<foo>")
        new_case.save()

        for k in dest_folder.glob("**/*"):
            if not k.is_file():
                continue
            try:
                ds = pydicom.dcmread(str(k), stop_before_pixels=True)
            except:
                continue
            k = DICOMInstance(
                study_uid=ds.StudyInstanceUID,
                series_uid=ds.SeriesInstanceUID,
                instance_uid=ds.SOPInstanceUID,
                json_metadata=ds.to_json(),
                file_location=str(k.relative_to(data_folder)),
                study_description=ds.get("StudyDescription"),
                series_description=ds.get("SeriesDescription"),
                patient_name=ds.get("PatientName"),
                case=new_case,
            )
            k.save()


def watch():
    while True:
        sleep(1)
        try:
            do_watch()
        except:
            logging.error("Failure in incoming")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
