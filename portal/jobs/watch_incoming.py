# import logging
from unittest.mock import NonCallableMagicMock
from loguru import logger
from pathlib import Path
import shutil
from time import sleep
import os

from django.conf import settings

from portal.jobs.load_dicoms_job import LoadDicomsJob
from portal.models import Case
from common.constants import GravisNames
from . import pipelines

# logging.basicConfig(filename='watch_incoming.log', filemode='a', format='%(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

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
            raise Exception(f"Incoming folder {incoming} does not exist.")

        for incoming_folder in list(folder_paths):
            try:
                # Delete .complete so the folder will not be included in another job
                complete_file_path = Path(incoming_folder) / f
                os.unlink(complete_file_path)
            except Exception as e:
                raise Exception(
                    f"Failed to delete .complete from {incoming_folder}."
                )
            LoadDicomsJob.enqueue_work(None,parameters=dict(incoming_folder=str(incoming_folder)))
    except Exception as e:
        logger.exception(
            f"Problem processing incoming folder {str(incoming)}. Error: {e}."
        )

def trigger_queued_cases():
    # print("trigger_queued_cases()")
    cases = Case.objects.filter(status=Case.CaseStatus.QUEUED)

    for case in cases:
        case.status = Case.CaseStatus.PROCESSING
        case.save()

        pipeline = None
        for type, func in pipelines.registered.items():
            if case.case_type in (type, type.label):
                pipeline = func
                break
        else:
            logger.error(f"Unknown case_type '{case.case_type}'")
            case.status = Case.CaseStatus.ERROR
            case.save()
            continue
            # TODO: send case to error folder
        try:
            pipeline(case)
        except:
            case.status = Case.CaseStatus.ERROR
            case.save()
            logger.exception(f"Initializing processing for case {case} failed.")


def delete_cases():
    try:
        cases = Case.objects.filter(status="DEL")
        for case in cases:
            print(f"Marked for deletion {case.id} {case.case_location}")
            shutil.rmtree(case.case_location)
            case.delete()
        
    except Exception as e:
        print(e)


def watch():
    logger.info("Incoming watcher booted.")
    while True:
        try:
            sleep(settings.INCOMING_SCAN_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, exiting.")
            break
        try:
            scan_incoming_folder()
        except:
            logger.exception("Failure in incoming")

        try:
            trigger_queued_cases()
        except:
            logger.exception("Error in queuing.")

        try:
            delete_cases()
        except:
            logger.error("Error in deleting.")

    # get_queue("default").enqueue_in(timedelta(seconds=2), watch)
