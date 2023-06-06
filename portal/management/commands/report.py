from pathlib import Path
import subprocess
from django.core.management.base import BaseCommand
from portal.models import Case


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('case',nargs="?",default=None)

    def handle(self, *args, **options):
        if not options['case']:
            cases = Case.objects.all()
            for c in cases:
                try:
                    du = subprocess.check_output(['du','-sh', Path(c.case_location) ]).split()[0].decode('utf-8')
                except:
                    du = "ERR"
                print("╞═",c,f"  <{du}>",sep="")
            return
        case = Case.objects.get(id=options['case'])
        du = subprocess.check_output(['du','-sh', Path(case.case_location) ]).split()[0].decode('utf-8')
        print("╭ Case ",case,f"  <{du}>",sep="")
        print('│ ', case.case_location)
        for j in case.processing_jobs.order_by("id").all():
            if j.result_sets.count():
                print("╞═╦═",j,sep="")
            else:
                print("╞═══",j,sep="")
            ct = j.result_sets.count()
            for i,dicom_set in enumerate(j.result_sets.all()):
                du = subprocess.check_output(['du','-sh', Path(case.case_location) / dicom_set.set_location ]).split()[0].decode('utf-8')
                print(f"│ {'╚' if i==ct-1 else '╠'}═══",dicom_set,f"  <{du}>", sep="")
