from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.docker_job import DockerJob
from portal.jobs.mark_case_ready import MarkCaseReadyJob
from portal.jobs.work_job import WorkJobView

import django_rq
from loguru import logger

def run(case):
    incoming_dicom_set = case.dicom_sets.get(origin="Incoming")
    _, rq_preview_job = GeneratePreviewsJob.enqueue_work(case, incoming_dicom_set)
    mets_job, rq_mets_job = DockerJob.enqueue_work(case, incoming_dicom_set, docker_image="mercureimaging/gravis-metsmaps")
    return MarkCaseReadyJob.enqueue_work(case, depends_on=[rq_preview_job, rq_mets_job])