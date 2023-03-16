# import logging
from unittest.mock import NonCallableMagicMock
from loguru import logger
from pathlib import Path
import shutil
from time import sleep
import os, json
from typing import Tuple
from uuid import uuid4

from django.conf import settings
from django.db import transaction

import django_rq

import portal.jobs.dicomset_utils as dicomset_utils
import portal.jobs.docker_utils as docker_utils
from portal.jobs.load_dicoms_job import LoadDicomsJob
from portal.models import Case, ProcessingJob
from common.constants import GravisNames, GravisFolderNames
from .cine_generation import GeneratePreviewsJob
from .work_job import do_job

from . import pipelines
from .utils import report_failure, report_success
import common.helper as helper

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

        for incoming_case in list(folder_paths):
            try:
                # Delete .complete so the folder will not be included in another job
                complete_file_path = Path(incoming_case) / f
                os.unlink(complete_file_path)
            except Exception as e:
                raise Exception(
                    f"Failed to delete .complete from {incoming_case}."
                )
            LoadDicomsJob.enqueue_work(None,parameters=dict(incoming_case=str(incoming_case)))
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

        if case.case_type not in pipelines.registered:
            logger.error(f"Unknown case_type {Case.case_type}")
            case.status = Case.CaseStatus.ERROR
            case.save()
            continue
            # TODO: send case to error folder
        try:
            pipelines.registered[case.case_type](case)
        except:
            case.status = Case.CaseStatus.ERROR
            case.save()
            logger.exception(f"Initializing processing for case {case} failed.")


def delete_cases():
    try:
        cases = Case.objects.filter(status="DEL")
        cases_locations_to_delete = []
        for case in cases:
            print(f"Marked for deletion {case.id} {case.case_location}")
            cases_locations_to_delete.append(case.case_location)
        cases.delete()
        for case_location in cases_locations_to_delete:
            shutil.rmtree(case_location)
        
    except Exception as e:
        print(e)


def watch():
    logger.info("Incoming watcher booted.")
    while True:
        sleep(settings.INCOMING_SCAN_INTERVAL)
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
