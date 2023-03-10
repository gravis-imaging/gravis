from .work_job import WorkJobView
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from .docker_utils import do_docker_job

class DockerJob(WorkJobView):
    type = "DOCKER"

    @classmethod
    def do_job(cls, job: ProcessingJob):
        do_docker_job(job)