import pytest
from .models import *
from django.conf import settings
from pathlib import Path 
from pyfakefs.fake_filesystem import FakeFilesystem

def test_example(fs: FakeFilesystem):
    fs.create_dir(Path(settings.INCOMING_FOLDER) / "test" )
    assert (Path(settings.INCOMING_FOLDER) / "test").exists()