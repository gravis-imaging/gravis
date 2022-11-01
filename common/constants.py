"""
constants.py
============
gravis-wide constants, used for standardizing key names and extensions.
"""

from enum import Enum

class GravisNames:
    LOCK = ".lock"
    PROCESSING = ".processing"
    COMPLETE = ".complete"
    ERROR = ".error"
    DCM = ".dcm"
    DCMFILTER = "*.dcm"


class GravisFolderNames:
    INPUT = "input"
    PROCESSED = "processed"
    FINDINGS = "findings"

    
class DockerReturnCodes(Enum):
    NO_ERRORS = 0
    INPUT_PATH_DOES_NOT_EXIST = 1
    NO_DICOMS_EXIST = 2
    DICOM_READING_ERROR = 3
    CANNOT_CALCULATE_INTENSITY_INDEX = 4
    INTENSITY_INDEX_SHOULD_BE_LESS_THAN_NUM_VOLUMES = 5
    ERROR_CALCULATING_SUBTRACTED_IMAGES = 6
    ERROR_CALCULATING_PROJECTIONS = 7
    ERROR_SAVING_FILES = 8

    def toDict():       
        return {k: v.value for k, v in DockerReturnCodes.__members__.items()}



