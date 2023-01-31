from pathlib import Path
from time import time
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from pydicom import Dataset, valuerep
from datetime import datetime
from django.conf import settings


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
        RECEIVED = "RCVD", "Received"
        QUEUED = "QUED", "Queued"
        PROCESSING = "PROC", "Processing"
        READY = "RDY", "Ready"
        VIEWING = "VIEW", "Viewing"
        COMPLETE = "COMP", "Complete"
        ARCHIVED = "ARCH", "Archived"
        ERROR = (
            "ERR",
            "Error",
        )  # initial db registration, copying to input, json check failure
        DELETE = "DEL", "Delete"

    patient_name = models.CharField(max_length=100, blank=True, null=True)
    mrn = models.CharField(max_length=100, blank=True, null=True)
    acc = models.CharField(max_length=100, blank=True, null=True)
    case_type = models.CharField(
        max_length=100, choices=CaseType.choices, blank=True, null=True
    )
    exam_time = models.DateTimeField(blank=True, null=True)
    receive_time = models.DateTimeField(default=timezone.now, blank=False)
    status = models.CharField(
        max_length=100, choices=CaseStatus.choices, default=CaseStatus.RECEIVED
    )
    num_spokes = models.CharField(max_length=1000, default="", blank=False, null=False)
    twix_id = models.CharField(max_length=1000, blank=True, null=True)
    case_location = models.CharField(max_length=10000, blank=False, null=False)
    settings = models.JSONField(null=True)  # use presets, smoothing, num_angles etc
    incoming_payload = models.JSONField(blank=False, null=False)
    last_read_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        related_name="last_read_by",
    )
    viewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        related_name="viewed_by",
    )

    class Meta:
        db_table = "gravis_case"


class ProcessingJob(models.Model):
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
        max_length=100, blank=True, null=True
    )  # pending, processing, success, fail, description
    error_description = models.CharField(max_length=1000, blank=True, null=True)
    json_result = models.JSONField(null=True)
    parameters = models.JSONField(null=True)
    dicom_set = models.ForeignKey("DICOMSet", on_delete=models.CASCADE, null=True, blank=True)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, null=True, blank=True)
    docker_image = models.CharField(max_length=100, blank=True, null=True)
    rq_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return "; ".join([f"{x}: {getattr(self,x)}" for x in "category parameters status error_description".split()])

    class Meta:
        db_table = "gravis_processing_job"
        # constraints = [
        #     models.CheckConstraint(
        #         check=models.Q(json_result__isnull=False)
        #         | models.Q(dicom_set__isnull=False),
        #         name="both_dicom_set_and_json_result_cannot_be_null",
        #     )
        # ]


class DICOMSet(models.Model):
    """
    A model to represent a DICOM set. A DICOM set usually has one DICOM study, but it is possible to have more than one.
    It will either be an input GRASP volume or the output of the processing step - MIP, subtractions.
    Located in /opt/gravis/cases/[UID]/input, /opt/gravis/cases/[UID]/processed
    """

    set_location = models.CharField(max_length=10000, null=False)
    created_at = models.DateTimeField(default=timezone.now, blank=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    origin = models.CharField(
        max_length=100, blank=False, null=False
    )  # Incoming, Processed
    type = models.CharField(
        max_length=100, blank=True, null=True
    )  # MIP, Subtraction, Onco
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="dicom_sets")
    processing_job = models.ForeignKey(
        ProcessingJob,
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        related_name="result_sets",
    )  # null if incoming, otherwise outcome of a processing step

    class Meta:
        db_table = "gravis_dicom_set"


class Finding(models.Model):
    dicom_set = models.ForeignKey(DICOMSet, on_delete=models.CASCADE, related_name="findings")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now, blank=True)

    name = models.CharField(max_length=100)
    file_location = models.CharField(null=True,max_length=1000)
    data = models.JSONField(null=True)

    def to_dict(self):
        return dict(
            url=str( Path(settings.MEDIA_URL) / Path(self.dicom_set.case.case_location).relative_to(settings.DATA_FOLDER) / self.file_location),
            name=self.name,
            created_at=self.created_at.timestamp()
        )
    class Meta:
        db_table = "gravis_finding"


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

    acquisition_seconds = models.FloatField(null=True)
    acquisition_number = models.IntegerField(null=True)
    series_number = models.IntegerField(null=True)
    slice_location = models.FloatField(null=True)
    num_frames = models.IntegerField(null=True, default=1)
    json_metadata = models.JSONField(null=False)
    dicom_set = models.ForeignKey(
        DICOMSet, on_delete=models.CASCADE, related_name="instances"
    )

    def __str__(self):
        return "; ".join([f"{x}: {getattr(self,x)}" for x in "series_number slice_location acquisition_seconds acquisition_number num_frames".split()])
        # return f"series_number {self.series_number}; slice_location {self.slice_location}; seconds: {self.acquisition_seconds}; acq_number: {self.acquisition_number}; num_frames: {self.num_frames}"

    @classmethod
    def from_dataset(cls, ds: Dataset):
        series_dt = datetime.combine(
            valuerep.DA(ds.SeriesDate), valuerep.TM(ds.SeriesTime)
        )
        study_dt = datetime.combine(
            valuerep.DA(ds.StudyDate), valuerep.TM(ds.StudyTime)
        )
        delta = series_dt - study_dt

        return DICOMInstance(
            study_uid=ds.StudyInstanceUID,
            series_uid=ds.SeriesInstanceUID,
            instance_uid=ds.SOPInstanceUID,
            acquisition_number=ds.get("AcquisitionNumber"),
            series_number=ds.get("SeriesNumber"),
            slice_location=ds.get("SliceLocation"),
            # instance_number=ds.get("InstanceNumber"),
            num_frames=ds.get("NumberOfFrames"),
            acquisition_seconds = delta.total_seconds(),
            json_metadata=ds.to_json(bulk_data_threshold=1024, bulk_data_element_handler=lambda _: ""),
        )

    class Meta:
        db_table = "gravis_dicom_instance"
        constraints = [
            models.UniqueConstraint(
                fields=["dicom_set", "study_uid", "series_uid", "instance_uid"],
                name="unique_uids",
            )
        ]
        indexes = [
            models.Index(fields=["series_uid", "acquisition_number"]),
            models.Index(fields=["study_uid", "series_number"]),
        ]


# class CaseHistory(models.Model):
#     """
#     A model to represent a Case History
#     """

#     action_time
#     reader
#     case
#     action


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)  
    privacy_mode = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
