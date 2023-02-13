from portal.jobs.cine_generation import GeneratePreviewsJob
from portal.jobs.send_findings import SendFindingsJob
from django.urls import path

urls = [
    path("job/preview", GeneratePreviewsJob.as_view()),
    path("job/send_findings", SendFindingsJob.as_view())
]
