from subprocess import Popen
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    """
    A quick command to start the webserver and worker processes together. This mixes the logs up, so of limited use, but is faster. 
    """
    def handle(self, *args, **options):
        commands = ["rqworker cheap", "rqworker default", "watcher", "runserver"]
        procs = [ Popen(["./manage.py", *i.split()]) for i in commands ]
        for p in procs:
            try:
                p.wait()
            except KeyboardInterrupt:
                pass