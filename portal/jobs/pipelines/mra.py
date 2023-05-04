from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.docker_job import DockerJob
from portal.jobs.mark_case_ready import MarkCaseReadyJob

def run(case):
    incoming_dicom_set = case.dicom_sets.get(origin="Incoming")    
    mra_job, rq_mra_job = DockerJob.enqueue_work(case, incoming_dicom_set, docker_image="mercureimaging/gravis-processing-mra:master")
    _, rq_preview_job = GeneratePreviewsJob.enqueue_work(case, incoming_dicom_set)
    _, rq_sub_preview_job = GeneratePreviewsJob.enqueue_work(case, depends_on=rq_mra_job,parameters=dict(source_type="SUB",source_job=mra_job.id))
    MarkCaseReadyJob.enqueue_work(case, depends_on=[rq_mra_job, rq_preview_job, rq_sub_preview_job])