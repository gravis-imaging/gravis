from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


# class DockerJob(models.Model):
#     docker_image = models.CharField(max_length=10000)
#     input_folder = models.CharField(max_length=10000)
#     output_folder = models.CharField(max_length=10000)
#     complete = models.BooleanField(default=False)

#     class Meta:
#         db_table = 'gravis_docker_job'


class Case(models.Model):
    """
    A model to represent a Gravis case.
    A case contains a GRASP data set and its processing results.
    A case's location: /opt/gravis/data/cases/[UID]
    """

    # TODO: create a config file that have settings (docker etc) for each case types
    class CaseType(models.TextChoices):
        MRA = "MRA", "GRASP MRA"
        ONCO = "Onco", "GRASP Onco"
        SVIEW = "SVW", "Series Viewer"

    class CaseStatus(models.TextChoices):
        RECEIVED = "RCVD", "RECEIVED"
        QUEUED = "QUED", "QUEUED"
        PROCESSING = "PROC", "PROCESSING"
        READY = "RDY", "READY"
        VIEWING = "VIEW", "VIEWING"
        COMPLETE = "COMP", "COMPLETE"
        ARCHIVED = "ARCH", "ARCHIVED"
        ERROR = "ERR", "ERROR"

    patient_name = models.CharField(max_length=100, blank=False, null=False)
    mrn = models.CharField(max_length=100, blank=False, null=False)
    acc = models.CharField(max_length=100, blank=False, null=False)
    case_type = models.CharField(
        max_length=4, choices=CaseType.choices, default=CaseType.MRA
    )
    exam_time = models.DateTimeField(blank=False, null=False)
    receive_time = models.DateTimeField(default=timezone.now, blank=False)
    status = models.CharField(
        max_length=4, choices=CaseStatus.choices, default=CaseStatus.RECEIVED
    )
    num_spokes = models.CharField(max_length=1000, default="", blank=True, null=True)
    twix_id = models.CharField(max_length=1000, blank=False, null=False)
    case_location = models.CharField(max_length=10000, blank=False, null=False)
    settings = models.JSONField(null=True)
    incoming_payload = models.JSONField(null=False)
    reader = models.ForeignKey(User, on_delete=models.SET_NULL, default=None, null=True)

    class Meta:
        db_table = "gravis_case"


class ProcessingResult(models.Model):
    """
    A model to represent processing results for a specific gravis case.
    Can have none, one or more DICOM set results or other result types -
    json, image.
    """

    created_at = models.DateTimeField(default=timezone.now, blank=True)
    category = models.CharField(
        max_length=100, blank=False, null=False
    )  # dicom set, json, image
    status = models.CharField(
        max_length=100, blank=False, null=False
    )  # success, fail, description
    json_result = models.JSONField(null=True)
    dicom_set = models.ForeignKey("DICOMSet", on_delete=models.CASCADE, null=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE)

    class Meta:
        db_table = "gravis_processing_result"
        constraints = [
            models.CheckConstraint(
                check=models.Q(json_result__isnull=False)
                | models.Q(dicom_set__isnull=False),
                name="both_dicom_set_and_json_result_cannot_be_null",
            )
        ]


class DICOMSet(models.Model):
    """
    A model to represent a DICOM set. A DICOM set usually has one DICOM study, but it is possible to have more than one.
    It will either be an input GRASP volume or the output of the processing step - MIP, subtractions.
    Located in /opt/gravis/cases/[UID]/input, /opt/gravis/cases/[UID]/processed
    """

    set_location = models.CharField(max_length=10000, null=False)
    created_at = models.DateTimeField(default=timezone.now, blank=True)
    type = models.CharField(
        max_length=100, blank=False, null=False
    )  # Incoming, MIP, subtraction
    case = models.ForeignKey(Case, on_delete=models.CASCADE)
    processing_result = models.ForeignKey(
        ProcessingResult, on_delete=models.SET_NULL, default=None, null=True
    )  # null if incoming, otherwise outcome of a processing step

    class Meta:
        db_table = "gravis_dicom_set"


class DICOMInstance(models.Model):
    """
    A model to represent a single DICOM slice.
    Located in /opt/gravis/cases/[UID]/input/slice.000.000.dcm
    """

    instance_location = models.CharField(
        max_length=10000, null=False
    )  # relative to cases/[UID]/<foo> folder
    study_uid = models.CharField(max_length=200)
    series_uid = models.CharField(max_length=200)
    instance_uid = models.CharField(max_length=200)
    json_metadata = models.JSONField(null=False)
    dicom_set = models.ForeignKey(DICOMSet, on_delete=models.CASCADE)

    class Meta:
        db_table = "gravis_dicom_instance"
        constraints = [
            models.UniqueConstraint(
                fields=["dicom_set", "study_uid", "series_uid", "instance_uid"],
                name="unique_uids",
            )
        ]
