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
                parameters={"undersample":4})
            job.save()
            result = django_rq.enqueue(
                do_job,
                args=(GeneratePreviewsJob,job.id),
                ) 
            job.rq_id = result.id
            job.save()
            print("ORI processing job",job.id)


            dicom_set_2 = case.dicom_sets.get(type="SUB")
            job_2 = ProcessingJob(
                status="CREATED", 
                category="CINE", 
                dicom_set=dicom_set_2,
                case = case,
                parameters={"undersample":4})
            job_2.save()
            result = django_rq.enqueue(
                do_job,
                args=(GeneratePreviewsJob,job_2.id),
                ) 
            job_2.rq_id = result.id
            job_2.save()
            print("SUB processing job",job_2.id)