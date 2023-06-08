from subprocess import Popen
from django.core.management.base import BaseCommand
from portal.endpoints.common import debug_sql
from portal.models import Case, DICOMInstance, DICOMSet, ProcessingJob
from django.db.models import Q
class Command(BaseCommand):
    """
    to help migration
    """
    @debug_sql
    def handle(self, *args, **options):
        dicom_sets = DICOMSet.objects.filter(Q(type__in=("ORI","SUB")) | Q(type__contains=("METS_"))).prefetch_related("instances")
        
        # id__in=(tuple({i.dicom_set_id for i in instances})))

        
        for d in dicom_sets:
            ins = d.instances.all()
            d.set_from_instance(ins[0])
            for i in ins:
                i.calc_position()
        dicom_sets.update(is_volume=True)
        # print(dicom_sets)