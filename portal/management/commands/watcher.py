from django.core.management.base import BaseCommand
from portal.jobs import watch_incoming

class Command(BaseCommand):
    def handle(self, *args, **options):
        watch_incoming.watch()
