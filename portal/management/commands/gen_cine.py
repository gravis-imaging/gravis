from django.core.management.base import BaseCommand

from portal.jobs.cine_generation import GeneratePreviewsJob, do_job
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob

import django_rq
class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('case')

    def handle(self, *args, **options):
        if options['case'] == "all":
            cases = Case.objects.all()
        else:
            cases = [Case.objects.get(id=options['case'])]
        
        if options['case'] == "all" and not input(f"Generate {cases.count()} sets of previews? "):
            print("Aborting.")
            return

        for case in cases:
            dicom_set = case.dicom_sets.get(origin="Incoming")
            job = ProcessingJob(
                status="CREATED", 
                category="CINE", 
                dicom_set=dicom_set,
                case = case,
                parameters={})
            job.save()
            result = django_rq.enqueue(
                do_job,
                args=(GeneratePreviewsJob,job.id),
                ) 
            job.rq_id = result.id
            job.save()