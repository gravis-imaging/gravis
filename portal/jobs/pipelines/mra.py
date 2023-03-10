from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.docker_job import DockerJob


def run(case):
    incoming_dicom_set = case.dicom_sets.get(origin="Incoming")    
    mra_job, rq_mra_job = DockerJob.enqueue_work(case, incoming_dicom_set, docker_image="gravis-processing-mra")
    GeneratePreviewsJob.enqueue_work(case, incoming_dicom_set)
    GeneratePreviewsJob.enqueue_work(case, depends_on=rq_mra_job,parameters=dict(source_type="SUB",source_job=mra_job.id))