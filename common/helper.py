"""
helper.py
=========
Various internal helper functions for gravis.
"""
# Standard python includes
from pathlib import Path
import uuid


class FileLock:
    """Helper class that implements a file lock. The lock file will be removed also from the destructor so that
    no spurious lock files remain if exceptions are raised."""

    def __init__(self, path_for_lockfile: Path):
        self.lockCreated = True
        self.lockfile = path_for_lockfile
        try:
            self.lockfile.touch(exist_ok=False)
        except:
            raise Exception(f"Unable to create lock file {path_for_lockfile}")

    # Destructor to ensure that the lock file gets deleted
    # if the calling function is left somewhere as result
    # of an unhandled exception
    def __del__(self) -> None:
        self.free()

    def free(self) -> None:
        try:
            if self.lockCreated:
                self.lockfile.unlink()
                self.lockCreated = False
        except:
            raise Exception(f"Unable to remove lock file {self.lockfile}.")

def generate_folder_name() -> str:
    new_uuid = str(uuid.uuid4())
    return new_uuid
