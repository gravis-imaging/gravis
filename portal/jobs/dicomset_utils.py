from loguru import logger
from pathlib import Path
from typing import Tuple
import os
import shutil

from common.constants import GravisNames
from portal.models import DICOMInstance, DICOMSet
import pydicom


def register(set_path, case, origin, job_id=None, type=""):

    # Register DICOM Set    
    try: 
        dcm = next(set_path.glob("**/*.dcm"))
    except:
        raise Exception(f"No DICOM files found in {set_path}")

    if type == "":
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
            imageType = ds.get("ImageType",[]) # SECONDARY/DERIVED/TYPE (eg)
            if len(imageType) > 2:
                type = ds.ImageType[2]
        except:
            raise Exception(
                f"Exception during dicom file reading. Cannot process incoming instance {str(dcm)}"
            )

    try:
        print(str(set_path), origin, type, case, job_id)
        dicom_set = DICOMSet(
            set_location=str(set_path),
            origin=origin,
            type=type,
            case=case,
            processing_job_id=job_id,
        )
        dicom_set.save()
    except:
        raise Exception(f"Cannot create a db table for incoming data set {set_path}")

    # Register DICOM Instances
    for dcm in set_path.glob("**/*.dcm"):
        if not dcm.is_file():
            continue
        try:
            ds = pydicom.dcmread(str(dcm), stop_before_pixels=True)
        except:
            raise Exception(
                f"Exception during dicom file reading. Cannot process incoming instance {str(dcm)}"
            )
        try:
            instance = DICOMInstance.from_dataset(ds)
            instance.instance_location = str(dcm.relative_to(set_path))
            instance.dicom_set = dicom_set
            instance.save()
            if not dicom_set.image_orientation_calc_inv:
                dicom_set.set_from_instance(instance)
        except:
            raise Exception(
                f"Exception during DICOMInstance model creation. Cannot process incoming instance {str(dcm)}"
            )
    return dicom_set

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
