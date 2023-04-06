from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.mark_case_ready import MarkCaseReadyJob

def run(case):
    incoming_dicom_set = case.dicom_sets.get(origin="Incoming")    
    _, rq_preview_job = GeneratePreviewsJob.enqueue_work(case, incoming_dicom_set)
    MarkCaseReadyJob.enqueue_work(case, depends_on=[rq_preview_job])