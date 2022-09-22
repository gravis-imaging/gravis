import logging
import os
import threading
from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"

    def ready(self):
        if os.environ.get("RUN_MAIN"):
            from .jobs import watch_incoming

            t = threading.Thread(target=watch_incoming.watch, daemon=True)
            t.start()
