from django.core.management.base import BaseCommand
from portal.models import Case
from portal.jobs.watch_incoming import trigger_queued_cases 


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('case')

    def handle(self, *args, **options):
        if options['case'] == "all":
            cases = Case.objects.all()
        else:
            cases = [Case.objects.get(id=options['case'])]
        for case in cases:
            case.status = Case.CaseStatus.QUEUED
            case.save()

        trigger_queued_cases()
