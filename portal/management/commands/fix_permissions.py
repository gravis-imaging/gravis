from django.core.management.base import BaseCommand
from portal.models import Case
from portal.jobs.watch_incoming import trigger_queued_cases 


class Command(BaseCommand):

    def handle(self, *args, **options):
        from django.contrib.auth.management import create_permissions
        from django.apps import apps
        create_permissions(apps.get_app_config('portal'))