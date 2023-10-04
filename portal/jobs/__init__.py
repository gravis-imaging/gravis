from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.send_findings import SendFindingsJob
from portal.jobs.fix_rotation_job import FixRotationJob

from django.urls import path

urls = [
    path("job/preview", GeneratePreviewsJob.as_view()),
    path("job/send_findings", SendFindingsJob.as_view()),
    path("job/rotate", FixRotationJob.as_view())
]
