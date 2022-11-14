
from .settings import *

DATA_FOLDER = "/tmp/data"
INCOMING_FOLDER = "/tmp/data/incoming"
CASES_FOLDER = "/tmp/data/cases"
ERROR_FOLDER = "/tmp/data/error"
USE_TZ = False
RQ_QUEUES = {
    "default": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0,
        # 'PASSWORD': 'some-password',
        "DEFAULT_TIMEOUT": 360,
    },
}
# Set up in memory databases for testing purposes
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}
