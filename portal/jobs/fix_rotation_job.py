import gzip
from pathlib import Path
from subprocess import Popen
from django.core.management.base import BaseCommand
from app import settings
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from django.db.models import Q
import pydicom
import numpy as np
from .work_job import WorkJobView

class FixRotationJob(WorkJobView):
    type = "FixRotationJob"
    queue = "cheap"

    @classmethod
    def do_job(cls, job):
        case = job.case
        k = job.parameters.get("n",1)
        dicom_set = case.dicom_sets.get(origin="Incoming")
        instances = dicom_set.instances
        print("Running...")
        for instance in instances.all():
            file_location = Path(settings.DATA_FOLDER) / dicom_set.set_location / instance.instance_location
            gz_location = file_location.with_suffix(file_location.suffix+".gz")
            print(file_location)
            if not file_location.exists() and gz_location.exists():
                with gzip.open(gz_location, 'r') as fp:
                    ds = pydicom.dcmread(fp)
                fp_write = gzip.open(gz_location, 'wb')
            else:
                ds = pydicom.dcmread(file_location)
                fp_write = open(file_location, 'wb')
            pixel_array = ds.pixel_array
            pixel_array = np.rot90(pixel_array, k=k)
            ds.PixelData = pixel_array.tobytes()
            ds.save_as(fp_write)
            fp_write.close()
        # print(dicom_sets)
