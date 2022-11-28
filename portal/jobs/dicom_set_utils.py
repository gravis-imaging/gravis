from loguru import logger
from pathlib import Path
from typing import Tuple
import os
import shutil

from common.constants import GravisNames
from portal.models import DICOMInstance, DICOMSet
import pydicom


def register(set_path: str, case, origin, type, job_id=None) -> Tuple[bool, str]:

    # Register DICOM Set
    logger.info(f"set_path {set_path}")
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
