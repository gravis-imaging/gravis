from django.core.management.commands.runserver import Command as RunserverCommand

# =======================
# What's going on here?
# This overrides the staticfiles app's override of the runserver command.
# We want to keep staticfiles around (for collectstatic) but staticfiles overrides the
# runserver command and insists on serving static files without using our middleware.
# We have to use our middleware throughout, at least in development mode, to set the 
# correct headers.

class Command(RunserverCommand):
    pass
