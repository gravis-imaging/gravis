from .work_job import WorkJobView
from portal.models import ProcessingJob
from loguru import logger
from pathlib import Path
from django.conf import settings
from portal.models import  ProcessingJob
import subprocess


class CompressJob(WorkJobView):
    type = "COMPRESS"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        for instance in job.dicom_set.instances.all():
            file_location = Path(settings.DATA_FOLDER) / job.dicom_set.set_location / instance.instance_location
            result = subprocess.run(["gzip", file_location], stdout=subprocess.PIPE, check=True)
            

