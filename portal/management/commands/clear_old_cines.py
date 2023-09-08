from django.core.management.base import BaseCommand
from portal.models import Case
from portal.jobs.watch_incoming import trigger_queued_cases 
import shutil
class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('case')

    def handle(self, *args, **options):
        sets = Case.objects.get(id=options['case']).dicom_sets.filter(type__contains='CINE').order_by("created_at")
        to_delete = list(sets)[:-3]
        print(sets)
        for set in sets:
            print(set.set_location)
        # for set in to_delete:
            # shutil.rmtree(set.set_location)
            # set.delete()
        # trigger_queued_cases()
