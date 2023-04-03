from portal.jobs.utils import send_success_notification
from .work_job import WorkJobView
from portal.models import Case

class MarkCaseReadyJob(WorkJobView):
    type = "MarkCaseReady"
    queue = "cheap"
    @classmethod
    def do_job(cls, job):
        job.case.status = Case.CaseStatus.READY
        job.case.save()
        send_success_notification(job)
