from django_rq.management.commands.rqworker import Command as RQCommand
from django_rq.settings import QUEUES_LIST

class Command(RQCommand):
    """
    For testing, listen on all queues if not given a particular queue to listen on.
    """
    def handle(self, *args, **options):
        if len(args) == 0:
            return super().handle( *[q["name"] for q in QUEUES_LIST], **options)
        return super().handle(*args,**options)